from __future__ import annotations

import numpy as np


def run_goal_monte_carlo(
    current_balance: float,
    monthly_contribution: float,
    target_amount: float,
    years: float,
    annual_return_mean: float = 0.08,
    annual_volatility: float = 0.16,
    num_sims: int = 10_000,
) -> dict[str, float]:
    months = max(1, int(years * 12))
    monthly_mu = (1.0 + annual_return_mean) ** (1.0 / 12.0) - 1.0
    monthly_sigma = annual_volatility / np.sqrt(12.0)

    # Geometric Brownian motion approximation at monthly granularity.
    shocks = np.random.normal(monthly_mu, monthly_sigma, size=(num_sims, months))
    growth = np.cumprod(1.0 + shocks, axis=1)
    contributions = monthly_contribution * np.cumsum(np.ones((num_sims, months)), axis=1)
    terminal_values = current_balance * growth[:, -1] + contributions[:, -1]

    success_probability = float(np.mean(terminal_values >= target_amount))
    expected_terminal = float(np.mean(terminal_values))
    shortfall = float(max(0.0, target_amount - np.percentile(terminal_values, 50)))

    if success_probability >= 0.95:
        recommended_contribution = monthly_contribution
    else:
        safety_ratio = target_amount / max(expected_terminal, 1.0)
        recommended_contribution = monthly_contribution * min(3.0, max(1.0, safety_ratio))

    return {
        "success_probability": success_probability,
        "expected_terminal_value": expected_terminal,
        "median_shortfall": shortfall,
        "recommended_monthly_contribution": float(recommended_contribution),
    }
