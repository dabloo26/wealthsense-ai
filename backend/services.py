from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from src.wealthsense_ai.simulation import run_goal_monte_carlo


def fetch_macro_snapshot() -> dict[str, float | date]:
    vix = yf.download("^VIX", period="3mo", progress=False, auto_adjust=False).dropna()
    if vix.empty:
        raise RuntimeError("Unable to fetch VIX data.")
    vix_close = float(vix["Close"].iloc[-1])
    as_of = pd.to_datetime(vix.index[-1]).date()

    fed = _fetch_fred_series("FEDFUNDS")
    cpi = _fetch_fred_series("CPIAUCSL")
    fed_latest = float(fed.iloc[-1]["value"])
    cpi_yoy = float((cpi.iloc[-1]["value"] / cpi.iloc[-13]["value"] - 1.0) * 100.0)
    return {
        "as_of": as_of,
        "vix_close": vix_close,
        "fed_funds_rate": fed_latest,
        "cpi_year_over_year": cpi_yoy,
    }


def live_forecast(ticker: str, horizon_days: int, macro: dict[str, float | date]) -> dict[str, object]:
    history = yf.download(ticker, period="3y", progress=False, auto_adjust=False).dropna()
    if history.empty:
        raise RuntimeError(f"No historical data for {ticker}")
    close = history["Close"].astype(float)
    returns = close.pct_change().dropna()
    annual_mu = float(returns.mean() * 252.0)
    annual_sigma = float(returns.std() * np.sqrt(252.0))

    # Macro-adjusted drift: high VIX reduces drift, stable fed/cpi slightly supports drift.
    macro_drift_adjust = (
        -0.001 * max(0.0, float(macro["vix_close"]) - 20.0)
        - 0.0005 * max(0.0, float(macro["fed_funds_rate"]) - 3.0)
        + 0.0002 * max(0.0, 3.0 - abs(float(macro["cpi_year_over_year"]) - 2.0))
    )
    daily_mu = (annual_mu / 252.0) + macro_drift_adjust
    daily_sigma = annual_sigma / np.sqrt(252.0)

    start_price = float(close.iloc[-1])
    paths = np.random.normal(loc=daily_mu, scale=max(1e-6, daily_sigma), size=(2000, horizon_days))
    projected = start_price * np.cumprod(1.0 + paths, axis=1)
    median = np.median(projected, axis=0)
    lower = np.percentile(projected, 10, axis=0)
    upper = np.percentile(projected, 90, axis=0)

    dates = pd.bdate_range(pd.Timestamp.today().normalize(), periods=horizon_days + 1)[1:]
    forecast_rows = [
        {
            "date": str(d.date()),
            "predicted": float(median[i]),
            "pred_lower": float(lower[i]),
            "pred_upper": float(upper[i]),
        }
        for i, d in enumerate(dates)
    ]
    return {
        "ticker": ticker,
        "latest_price": start_price,
        "horizon_days": horizon_days,
        "macro": macro,
        "forecast": forecast_rows,
    }


def compute_goal_plan(payload: dict[str, float | int]) -> dict[str, float]:
    return run_goal_monte_carlo(
        current_balance=float(payload["current_balance"]),
        monthly_contribution=float(payload["monthly_contribution"]),
        target_amount=float(payload["target_amount"]),
        years=float(payload["years"]),
        annual_return_mean=float(payload["annual_return_mean"]),
        annual_volatility=float(payload["annual_volatility"]),
        num_sims=int(payload["simulations"]),
    )


def _fetch_fred_series(series_id: str) -> pd.DataFrame:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    df = pd.read_csv(pd.io.common.StringIO(resp.text))
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    out = df.dropna().reset_index(drop=True)
    if out.empty:
        raise RuntimeError(f"Empty FRED series: {series_id}")
    return out

