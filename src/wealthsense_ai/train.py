from __future__ import annotations

import json
import random
from dataclasses import asdict

import numpy as np
import pandas as pd
import torch
import yfinance as yf
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .config import DataConfig, PathsConfig, TrainConfig
from .data import PreparedTickerData, prepare_ticker_data, reconstruct_prices
from .models import GRURegressor, LSTMRegressor, TransformerRegressor
from .regime import detect_market_regime
from .strategy import directional_accuracy, evaluate_buy_and_hold, evaluate_trading_strategy
from .tft_model import TFTRegressor
from .uncertainty import (
    apply_conformal_correction,
    calibration_report,
    conformal_quantile,
    interval_coverage,
    mc_dropout_predict,
    regime_adjusted_intervals,
)


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
) -> tuple[nn.Module, float, int]:
    criterion = nn.MSELoss()
    optim = torch.optim.AdamW(
        model.parameters(),
        lr=train_cfg.learning_rate,
        weight_decay=train_cfg.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optim, mode="min", patience=5, factor=0.5
    )
    model.to(device)
    best_loss = float("inf")
    best_state = None
    patience_left = train_cfg.patience

    stop_epoch = train_cfg.epochs
    for epoch in range(train_cfg.epochs):
        model.train()
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optim.zero_grad(set_to_none=True)
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optim.step()

        model.eval()
        val_losses = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device)
                pred = model(xb)
                val_losses.append(criterion(pred, yb).item())
        epoch_val = float(np.mean(val_losses))
        scheduler.step(epoch_val)
        if epoch_val < best_loss:
            best_loss = epoch_val
            best_state = model.state_dict()
            patience_left = train_cfg.patience
        else:
            patience_left -= 1
            if patience_left <= 0:
                stop_epoch = epoch + 1
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    return model, best_loss, stop_epoch


def _predict(model: nn.Module, x: np.ndarray, device: torch.device) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        xb = torch.tensor(x, dtype=torch.float32, device=device)
        return model(xb).detach().cpu().numpy()


def _returns_to_prices(last_known_price: float, predicted_returns: np.ndarray) -> np.ndarray:
    prices = [float(last_known_price)]
    for r in predicted_returns:
        prices.append(prices[-1] * float(np.exp(r)))
    return np.array(prices[1:], dtype=float)


def _latest_close_scalar(ticker: str) -> float:
    raw = yf.download(ticker, period="1d", auto_adjust=False, progress=False)["Close"].iloc[-1]
    if hasattr(raw, "iloc"):
        try:
            return float(raw.iloc[0])
        except Exception:
            return float(np.asarray(raw).reshape(-1)[0])
    return float(raw)


def _dynamic_ensemble(
    test_pred_map: dict[str, np.ndarray],
    val_pred_map: dict[str, np.ndarray],
    val_true: np.ndarray,
    rolling_window: int = 21,
) -> tuple[np.ndarray, dict[str, float]]:
    model_names = list(test_pred_map.keys())
    n_val = len(val_true)
    if n_val >= rolling_window:
        recent_errors = {}
        for name in model_names:
            recent_preds = val_pred_map[name][-rolling_window:]
            recent_true = val_true[-rolling_window:]
            recent_errors[name] = float(np.sqrt(np.mean((recent_true - recent_preds) ** 2)))
        inv = np.array([1.0 / max(recent_errors[m], 1e-8) for m in model_names])
        weights = inv / inv.sum()
    else:
        weights = np.ones(len(model_names)) / len(model_names)

    ensemble = np.zeros(len(next(iter(test_pred_map.values()))))
    for i, name in enumerate(model_names):
        ensemble += weights[i] * test_pred_map[name]
    return ensemble, dict(zip(model_names, weights.tolist()))


def _stacking_ensemble(
    test_pred_map: dict[str, np.ndarray],
    val_pred_map: dict[str, np.ndarray],
    val_true: np.ndarray,
) -> tuple[np.ndarray, dict[str, float]]:
    model_names = list(test_pred_map.keys())
    x_val = np.column_stack([val_pred_map[m] for m in model_names])
    x_test = np.column_stack([test_pred_map[m] for m in model_names])
    meta = Ridge(alpha=1.0)
    meta.fit(x_val, val_true)
    ensemble = meta.predict(x_test)
    weights = {name: float(coef) for name, coef in zip(model_names, meta.coef_)}
    weights["intercept"] = float(meta.intercept_)
    return ensemble, weights


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
        "tft": TFTRegressor(
            input_size=input_size,
            hidden_size=train_cfg.hidden_size,
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
) -> tuple[dict[str, float], pd.DataFrame, dict[str, float], np.ndarray, np.ndarray, int, dict[str, float], dict[str, float]]:
    train_loader = _to_loader(ticker_data.train_x, ticker_data.train_y, train_cfg.batch_size, True)
    val_loader = _to_loader(ticker_data.val_x, ticker_data.val_y, train_cfg.batch_size, False)
    model, _, stop_epoch = _train_model(model, train_loader, val_loader, train_cfg, device)

    val_preds, val_lower, val_upper, val_samples = mc_dropout_predict(model, ticker_data.val_x, device=device, n_samples=100)
    preds, lower, upper, test_samples = mc_dropout_predict(model, ticker_data.test_x, device=device, n_samples=100)
    truth = ticker_data.test_y
    val_truth = ticker_data.val_y
    current_vix = _latest_close_scalar("^VIX")
    val_lower, val_upper = regime_adjusted_intervals(val_lower, val_upper, current_vix=current_vix)
    lower, upper = regime_adjusted_intervals(lower, upper, current_vix=current_vix)
    qhat = conformal_quantile(y_cal=val_truth, lower_cal=val_lower, upper_cal=val_upper, alpha=0.1)
    lower, upper = apply_conformal_correction(lower, upper, qhat=qhat)
    calib = calibration_report(truth, test_samples)

    mae = float(mean_absolute_error(truth, preds))
    rmse = float(np.sqrt(mean_squared_error(truth, preds)))
    mape = float(mean_absolute_percentage_error(truth, preds))
    dacc = directional_accuracy(truth, preds)
    coverage = interval_coverage(truth, lower, upper)
    last_train_price = float(
        ticker_data.full_frame.loc[
            ticker_data.full_frame["Date"] < ticker_data.test_dates.iloc[0],
            "Close",
        ].iloc[-1]
    )
    reconstructed_prices = reconstruct_prices(last_train_price, preds)
    actual_prices = reconstruct_prices(last_train_price, truth)
    lower_prices = reconstruct_prices(last_train_price, lower)
    upper_prices = reconstruct_prices(last_train_price, upper)
    strategy = evaluate_trading_strategy(actual_prices=actual_prices, predicted_prices=reconstructed_prices)

    torch.save(model.state_dict(), paths.model_dir / f"{ticker_data.ticker}_{model_name}.pt")

    forecast_df = pd.DataFrame(
        {
            "date": ticker_data.test_dates.values,
            "ticker": ticker_data.ticker,
            "model": model_name,
            "actual_return": truth,
            "predicted_return": preds,
            "pred_lower_return": lower,
            "pred_upper_return": upper,
            "reconstructed_price": reconstructed_prices,
            "actual_price_reconstructed": actual_prices,
            "actual": truth,
            "predicted": preds,
            "pred_lower": lower_prices,
            "pred_upper": upper_prices,
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
    interval_debug = {
        "width_mean": float(np.mean(upper - lower)),
        "width_p90": float(np.percentile(upper - lower, 90)),
        "vix": current_vix,
        "conformal_qhat": float(qhat),
        "width_vix_40_mean": float(np.mean((upper - lower) * (2.2 / (1.0 if current_vix < 15 else 1.3 if current_vix < 25 else 1.7 if current_vix < 35 else 2.2)))),
    }
    return row, forecast_df, strategy, preds, val_preds, stop_epoch, calib, interval_debug


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
    training_debug: dict[str, object] = {}

    for ticker in data_cfg.tickers:
        ticker_data = prepare_ticker_data(data_cfg=data_cfg, paths_cfg=paths, ticker=ticker)
        model_map = _build_models(input_size=len(data_cfg.feature_columns), train_cfg=train_cfg)
        test_pred_map: dict[str, np.ndarray] = {}
        val_pred_map: dict[str, np.ndarray] = {}
        val_rmse_map: dict[str, float] = {}
        for model_name, model in model_map.items():
            metric_row, forecast_df, strategy, test_preds, val_preds, stop_epoch, calib, interval_debug = _evaluate_one(
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
            training_debug[f"{ticker}_{model_name}"] = {"early_stop_epoch": stop_epoch, "calibration": calib, "interval_debug": interval_debug}
            print(f"{ticker} {model_name} early_stopped_at_epoch={stop_epoch}")

        ensemble_test, ensemble_weights = _stacking_ensemble(test_pred_map, val_pred_map, ticker_data.val_y)
        ensemble_val, _ = _dynamic_ensemble(val_pred_map, val_pred_map, ticker_data.val_y, rolling_window=21)

        ens_mae = float(mean_absolute_error(ticker_data.test_y, ensemble_test))
        ens_rmse = float(np.sqrt(mean_squared_error(ticker_data.test_y, ensemble_test)))
        ens_mape = float(mean_absolute_percentage_error(ticker_data.test_y, ensemble_test))
        ens_dacc = directional_accuracy(ticker_data.test_y, ensemble_test)
        # Approximate interval from ensemble val residual spread.
        resid = np.abs(ticker_data.val_y - ensemble_val)
        ens_radius = float(np.quantile(resid, 0.9))
        ens_lower = ensemble_test - ens_radius
        ens_upper = ensemble_test + ens_radius
        ens_cov = interval_coverage(ticker_data.test_y, ens_lower, ens_upper)
        last_known_price = float(ticker_data.full_frame["Close"].iloc[-len(ticker_data.test_y) - 1])
        ens_pred_prices = reconstruct_prices(last_known_price, ensemble_test)
        ens_true_prices = reconstruct_prices(last_known_price, ticker_data.test_y)
        ens_strategy = evaluate_trading_strategy(actual_prices=ens_true_prices, predicted_prices=ens_pred_prices)
        buy_hold = evaluate_buy_and_hold(ens_true_prices)

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
                    "predicted_return": ensemble_test,
                    "pred_lower_return": ens_lower,
                    "pred_upper_return": ens_upper,
                    "reconstructed_price": ens_pred_prices,
                    "actual_price_reconstructed": ens_true_prices,
                    "actual": ticker_data.test_y,
                    "predicted": ensemble_test,
                    "pred_lower": reconstruct_prices(last_known_price, ens_lower),
                    "pred_upper": reconstruct_prices(last_known_price, ens_upper),
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
        training_debug[f"{ticker}_ensemble_weights"] = ensemble_weights
        print(f"{ticker} ensemble weights: {ensemble_weights}")

    metrics_df = pd.DataFrame(metric_rows)
    forecasts_df = pd.concat(forecast_frames, ignore_index=True)
    strategy_df = pd.DataFrame(strategy_rows)

    vix_now = _latest_close_scalar("^VIX")
    vix_regime = "calm" if vix_now < 15 else "moderate" if vix_now < 25 else "elevated" if vix_now < 35 else "crisis"
    spy = prepare_ticker_data(data_cfg=data_cfg, paths_cfg=paths, ticker="SPY")
    regime = detect_market_regime(
        returns=spy.full_frame["Log_Return"].values,
        vix=spy.full_frame.get("VIX_Zscore", pd.Series(np.zeros(len(spy.full_frame)))).values,
        volume=spy.full_frame["Volume"].values,
    )
    with paths.metrics_file.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "data_config": asdict(data_cfg),
                "train_config": asdict(train_cfg),
                "device": str(device),
                "results": metrics_df.to_dict(orient="records"),
                "training_debug": training_debug,
                "current_vix": vix_now,
                "vix_regime": vix_regime,
                "market_regime": regime,
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
    print(f"Current VIX regime at training: {vix_regime} ({vix_now:.2f})")


if __name__ == "__main__":
    run_training_pipeline()
