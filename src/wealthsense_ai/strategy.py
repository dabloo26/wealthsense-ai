from __future__ import annotations

import numpy as np
import pandas as pd


def evaluate_trading_strategy(
    actual_prices: np.ndarray,
    predicted_prices: np.ndarray,
    initial_capital: float = 10_000.0,
) -> dict[str, float]:
    if len(actual_prices) < 3:
        return {"cumulative_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0}

    actual_returns = np.diff(actual_prices) / np.maximum(actual_prices[:-1], 1e-8)
    pred_returns = np.diff(predicted_prices) / np.maximum(predicted_prices[:-1], 1e-8)

    signal = np.where(pred_returns > 0.0, 1.0, 0.0)
    strat_returns = signal * actual_returns[: len(signal)]

    equity = initial_capital * np.cumprod(1.0 + strat_returns)
    running_max = np.maximum.accumulate(equity)
    drawdown = (equity - running_max) / np.maximum(running_max, 1e-8)

    excess = strat_returns - (0.02 / 252.0)
    sharpe = 0.0 if np.std(excess) == 0.0 else np.sqrt(252.0) * np.mean(excess) / np.std(excess)

    return {
        "cumulative_return": float((equity[-1] / initial_capital) - 1.0),
        "sharpe_ratio": float(sharpe),
        "max_drawdown": float(drawdown.min()),
    }


def evaluate_buy_and_hold(actual_prices: np.ndarray, initial_capital: float = 10_000.0) -> dict[str, float]:
    if len(actual_prices) < 2:
        return {"cumulative_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0}

    returns = np.diff(actual_prices) / np.maximum(actual_prices[:-1], 1e-8)
    equity = initial_capital * np.cumprod(1.0 + returns)
    running_max = np.maximum.accumulate(equity)
    drawdown = (equity - running_max) / np.maximum(running_max, 1e-8)

    excess = returns - (0.02 / 252.0)
    sharpe = 0.0 if np.std(excess) == 0.0 else np.sqrt(252.0) * np.mean(excess) / np.std(excess)

    return {
        "cumulative_return": float((equity[-1] / initial_capital) - 1.0),
        "sharpe_ratio": float(sharpe),
        "max_drawdown": float(drawdown.min()),
    }


def directional_accuracy(actual: np.ndarray, pred: np.ndarray) -> float:
    actual_sign = np.sign(np.diff(actual))
    pred_sign = np.sign(np.diff(pred))
    if len(actual_sign) == 0:
        return 0.0
    return float(np.mean(actual_sign == pred_sign))


def summarize_forecasts(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby(["ticker", "model"], as_index=False).agg(
        mae=("mae", "mean"),
        rmse=("rmse", "mean"),
        mape=("mape", "mean"),
        directional_accuracy=("directional_accuracy", "mean"),
    )
    return grouped.sort_values(["ticker", "mape"], ascending=[True, True])
