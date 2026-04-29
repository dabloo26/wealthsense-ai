from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def detect_forecast_drift(
    forecasts_path: str,
    baseline_mae: float,
    threshold_multiplier: float = 2.0,
    lookback: int = 100,
) -> dict[str, float | bool]:
    path = Path(forecasts_path)
    if not path.exists():
        return {"drift_detected": False, "rolling_mae": 0.0, "baseline_mae": baseline_mae, "threshold": baseline_mae * threshold_multiplier}

    df = pd.read_csv(path)
    if df.empty or "actual" not in df.columns or "predicted" not in df.columns:
        return {"drift_detected": False, "rolling_mae": 0.0, "baseline_mae": baseline_mae, "threshold": baseline_mae * threshold_multiplier}

    recent = df.tail(lookback)
    rolling_mae = float(np.mean(np.abs(recent["actual"].astype(float) - recent["predicted"].astype(float))))
    threshold = float(baseline_mae * threshold_multiplier)
    return {
        "drift_detected": bool(rolling_mae > threshold),
        "rolling_mae": rolling_mae,
        "baseline_mae": float(baseline_mae),
        "threshold": threshold,
    }
