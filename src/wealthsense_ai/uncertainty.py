from __future__ import annotations

import numpy as np


def conformal_quantile(y_true: np.ndarray, y_pred: np.ndarray, alpha: float = 0.1) -> float:
    abs_errors = np.abs(y_true - y_pred)
    # 1-alpha central interval half-width.
    return float(np.quantile(abs_errors, 1.0 - alpha))


def apply_prediction_interval(pred: np.ndarray, radius: float) -> tuple[np.ndarray, np.ndarray]:
    return pred - radius, pred + radius


def interval_coverage(y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    covered = (y_true >= lower) & (y_true <= upper)
    return float(np.mean(covered))

