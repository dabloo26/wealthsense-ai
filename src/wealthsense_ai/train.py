from __future__ import annotations

import json
import random
from dataclasses import asdict

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .config import DataConfig, PathsConfig, TrainConfig
from .data import PreparedTickerData, prepare_ticker_data
from .models import GRURegressor, LSTMRegressor, TransformerRegressor
from .strategy import directional_accuracy, evaluate_buy_and_hold, evaluate_trading_strategy
from .uncertainty import apply_prediction_interval, conformal_quantile, interval_coverage


def _seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def _to_loader(x: np.ndarray, y: np.ndarray, batch_size: int, shuffle: bool) -> DataLoader:
    ds = TensorDataset(torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.float32))
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle)


def _train_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    train_cfg: TrainConfig,
    device: torch.device,
) -> tuple[nn.Module, float]:
    criterion = nn.MSELoss()
    optim = torch.optim.AdamW(
        model.parameters(),
        lr=train_cfg.learning_rate,
        weight_decay=train_cfg.weight_decay,
    )
    model.to(device)
    best_loss = float("inf")
    best_state = None
    patience_left = train_cfg.patience

    for _ in range(train_cfg.epochs):
        model.train()
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optim.zero_grad(set_to_none=True)
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optim.step()

        model.eval()
        val_losses = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device)
                pred = model(xb)
                val_losses.append(criterion(pred, yb).item())
        epoch_val = float(np.mean(val_losses))
        if epoch_val < best_loss:
            best_loss = epoch_val
            best_state = model.state_dict()
            patience_left = train_cfg.patience
        else:
            patience_left -= 1
            if patience_left <= 0:
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    return model, best_loss


def _predict(model: nn.Module, x: np.ndarray, device: torch.device) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        xb = torch.tensor(x, dtype=torch.float32, device=device)
        return model(xb).detach().cpu().numpy()


def _build_models(input_size: int, train_cfg: TrainConfig) -> dict[str, nn.Module]:
    return {
        "lstm": LSTMRegressor(
            input_size=input_size,
            hidden_size=train_cfg.hidden_size,
            num_layers=train_cfg.num_layers,
            dropout=train_cfg.dropout,
        ),
        "gru": GRURegressor(
            input_size=input_size,
            hidden_size=train_cfg.hidden_size,
            num_layers=train_cfg.num_layers,
            dropout=train_cfg.dropout,
        ),
        "transformer": TransformerRegressor(
            input_size=input_size,
            model_dim=train_cfg.transformer_dim,
            heads=train_cfg.transformer_heads,
            num_layers=2,
            dropout=train_cfg.dropout,
        ),
    }


def _evaluate_one(
    ticker_data: PreparedTickerData,
    model_name: str,
    model: nn.Module,
    train_cfg: TrainConfig,
    paths: PathsConfig,
    device: torch.device,
) -> tuple[dict[str, float], pd.DataFrame, dict[str, float], np.ndarray, np.ndarray]:
    train_loader = _to_loader(ticker_data.train_x, ticker_data.train_y, train_cfg.batch_size, True)
    val_loader = _to_loader(ticker_data.val_x, ticker_data.val_y, train_cfg.batch_size, False)
    model, _ = _train_model(model, train_loader, val_loader, train_cfg, device)

    val_preds = _predict(model, ticker_data.val_x, device=device)
    preds = _predict(model, ticker_data.test_x, device=device)
    truth = ticker_data.test_y
    val_truth = ticker_data.val_y
    interval_radius = conformal_quantile(val_truth, val_preds, alpha=0.1)
    lower, upper = apply_prediction_interval(preds, interval_radius)

    mae = float(mean_absolute_error(truth, preds))
    rmse = float(np.sqrt(mean_squared_error(truth, preds)))
    mape = float(mean_absolute_percentage_error(truth, preds))
    dacc = directional_accuracy(truth, preds)
    coverage = interval_coverage(truth, lower, upper)
    strategy = evaluate_trading_strategy(actual_prices=truth, predicted_prices=preds)

    torch.save(model.state_dict(), paths.model_dir / f"{ticker_data.ticker}_{model_name}.pt")

    forecast_df = pd.DataFrame(
        {
            "date": ticker_data.test_dates.values,
            "ticker": ticker_data.ticker,
            "model": model_name,
            "actual": truth,
            "predicted": preds,
            "pred_lower": lower,
            "pred_upper": upper,
            "mae": mae,
            "rmse": rmse,
            "mape": mape,
            "directional_accuracy": dacc,
            "interval_coverage": coverage,
        }
    )
    row = {
        "ticker": ticker_data.ticker,
        "model": model_name,
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "directional_accuracy": dacc,
        "interval_coverage": coverage,
    }
    return row, forecast_df, strategy, preds, val_preds


def run_training_pipeline() -> None:
    data_cfg = DataConfig()
    train_cfg = TrainConfig()
    paths = PathsConfig()
    paths.ensure()
    _seed_all(train_cfg.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    metric_rows: list[dict[str, float]] = []
    forecast_frames: list[pd.DataFrame] = []
    strategy_rows: list[dict[str, float]] = []

    for ticker in data_cfg.tickers:
        ticker_data = prepare_ticker_data(data_cfg=data_cfg, paths_cfg=paths, ticker=ticker)
        model_map = _build_models(input_size=len(data_cfg.feature_columns), train_cfg=train_cfg)
        test_pred_map: dict[str, np.ndarray] = {}
        val_pred_map: dict[str, np.ndarray] = {}
        val_rmse_map: dict[str, float] = {}
        for model_name, model in model_map.items():
            metric_row, forecast_df, strategy, test_preds, val_preds = _evaluate_one(
                ticker_data=ticker_data,
                model_name=model_name,
                model=model,
                train_cfg=train_cfg,
                paths=paths,
                device=device,
            )
            metric_rows.append(metric_row)
            forecast_frames.append(forecast_df)
            strategy_rows.append({"ticker": ticker, "model": model_name, **strategy})
            test_pred_map[model_name] = test_preds
            val_pred_map[model_name] = val_preds
            val_rmse_map[model_name] = float(np.sqrt(mean_squared_error(ticker_data.val_y, val_preds)))

        # Inverse-RMSE weighted ensemble for stronger robustness.
        model_names = list(test_pred_map.keys())
        inv = np.array([1.0 / max(val_rmse_map[m], 1e-8) for m in model_names])
        weights = inv / inv.sum()
        ensemble_test = np.sum([weights[i] * test_pred_map[m] for i, m in enumerate(model_names)], axis=0)
        ensemble_val = np.sum([weights[i] * val_pred_map[m] for i, m in enumerate(model_names)], axis=0)

        ens_mae = float(mean_absolute_error(ticker_data.test_y, ensemble_test))
        ens_rmse = float(np.sqrt(mean_squared_error(ticker_data.test_y, ensemble_test)))
        ens_mape = float(mean_absolute_percentage_error(ticker_data.test_y, ensemble_test))
        ens_dacc = directional_accuracy(ticker_data.test_y, ensemble_test)
        ens_radius = conformal_quantile(ticker_data.val_y, ensemble_val, alpha=0.1)
        ens_lower, ens_upper = apply_prediction_interval(ensemble_test, ens_radius)
        ens_cov = interval_coverage(ticker_data.test_y, ens_lower, ens_upper)
        ens_strategy = evaluate_trading_strategy(actual_prices=ticker_data.test_y, predicted_prices=ensemble_test)
        buy_hold = evaluate_buy_and_hold(ticker_data.test_y)

        metric_rows.append(
            {
                "ticker": ticker,
                "model": "ensemble",
                "mae": ens_mae,
                "rmse": ens_rmse,
                "mape": ens_mape,
                "directional_accuracy": ens_dacc,
                "interval_coverage": ens_cov,
            }
        )
        forecast_frames.append(
            pd.DataFrame(
                {
                    "date": ticker_data.test_dates.values,
                    "ticker": ticker,
                    "model": "ensemble",
                    "actual": ticker_data.test_y,
                    "predicted": ensemble_test,
                    "pred_lower": ens_lower,
                    "pred_upper": ens_upper,
                    "mae": ens_mae,
                    "rmse": ens_rmse,
                    "mape": ens_mape,
                    "directional_accuracy": ens_dacc,
                    "interval_coverage": ens_cov,
                }
            )
        )
        strategy_rows.append({"ticker": ticker, "model": "ensemble", **ens_strategy})
        strategy_rows.append({"ticker": ticker, "model": "buy_and_hold", **buy_hold})

    metrics_df = pd.DataFrame(metric_rows)
    forecasts_df = pd.concat(forecast_frames, ignore_index=True)
    strategy_df = pd.DataFrame(strategy_rows)

    with paths.metrics_file.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "data_config": asdict(data_cfg),
                "train_config": asdict(train_cfg),
                "device": str(device),
                "results": metrics_df.to_dict(orient="records"),
            },
            f,
            indent=2,
            default=str,
        )

    forecasts_df.to_csv(paths.forecasts_file, index=False)
    strategy_df.to_csv(paths.strategy_file, index=False)
    print(f"Saved metrics to {paths.metrics_file}")
    print(f"Saved forecasts to {paths.forecasts_file}")
    print(f"Saved strategy results to {paths.strategy_file}")


if __name__ == "__main__":
    run_training_pipeline()
