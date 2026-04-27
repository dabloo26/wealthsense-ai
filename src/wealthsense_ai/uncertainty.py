from __future__ import annotations

import numpy as np
import torch
from torch import nn


def mc_dropout_predict(
    model: nn.Module,
    x: np.ndarray,
    device: torch.device,
    n_samples: int = 100,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Run model n_samples times with dropout active.
    Returns (mean, lower_10th_pct, upper_90th_pct, all_samples).
    """
    model.train()
    samples = []
    xb = torch.tensor(x, dtype=torch.float32, device=device)
    with torch.no_grad():
        for _ in range(n_samples):
            pred = model(xb).detach().cpu().numpy()
            samples.append(pred)
    model.eval()
    sample_arr = np.stack(samples, axis=0)
    mean = sample_arr.mean(axis=0)
    lower = np.percentile(sample_arr, 10, axis=0)
    upper = np.percentile(sample_arr, 90, axis=0)
    return mean, lower, upper, sample_arr


def regime_adjusted_intervals(
    lower: np.ndarray,
    upper: np.ndarray,
    current_vix: float,
) -> tuple[np.ndarray, np.ndarray]:
    if current_vix < 15:
        multiplier = 1.0
    elif current_vix < 25:
        multiplier = 1.3
    elif current_vix < 35:
        multiplier = 1.7
    else:
        multiplier = 2.2

    midpoint = (upper + lower) / 2
    half_width = (upper - lower) / 2 * multiplier
    return midpoint - half_width, midpoint + half_width


def interval_coverage(y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    covered = (y_true >= lower) & (y_true <= upper)
    return float(np.mean(covered))


def calibration_report(
    y_true: np.ndarray,
    samples: np.ndarray,
    alphas: list[float] = [0.1, 0.2, 0.5],
) -> dict[str, float]:
    report: dict[str, float] = {}
    for alpha in alphas:
        lower = np.percentile(samples, alpha * 50, axis=0)
        upper = np.percentile(samples, 100 - alpha * 50, axis=0)
        coverage = float(np.mean((y_true >= lower) & (y_true <= upper)))
        target = 1.0 - alpha
        report[f"target_{int(target * 100)}pct"] = target
        report[f"actual_{int(target * 100)}pct"] = coverage
        report[f"calibration_error_{int(target * 100)}pct"] = abs(coverage - target)
    return report

