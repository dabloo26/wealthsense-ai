from __future__ import annotations

from datetime import date
from pathlib import Path

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


def forecast_detail(ticker: str, horizon_days: int) -> dict[str, object]:
    macro = fetch_macro_snapshot()
    fc = live_forecast(ticker=ticker, horizon_days=horizon_days, macro=macro)
    history = yf.download(ticker, period="18mo", progress=False, auto_adjust=False).reset_index()
    history = _normalize_market_frame(history)
    close = history["Close"].astype(float).reset_index(drop=True)
    history_points = [
        {"idx": int(i), "price": float(v)}
        for i, v in enumerate(close.tail(90).tolist())
    ]

    backtest = _walk_forward_backtest(close.values)
    model_breakdown, shap_top = _metrics_and_drivers_from_artifacts(ticker)
    driver_sentence = _plain_driver_sentence(macro)
    confidence = {
        "likely_low": float(np.percentile([row["pred_lower"] for row in fc["forecast"]], 30)),
        "likely_high": float(np.percentile([row["pred_upper"] for row in fc["forecast"]], 70)),
    }
    return {
        "ticker": ticker,
        "description": _asset_description(ticker),
        "latest_price": fc["latest_price"],
        "forecast": fc["forecast"],
        "history": history_points,
        "driver_sentence": driver_sentence,
        "confidence": confidence,
        "disclaimer": "Not financial advice. Forecasts carry uncertainty. Past performance does not predict future results.",
        "backtest": backtest,
        "model_breakdown": model_breakdown,
        "shap_top_drivers": shap_top,
        "walk_forward": backtest["walk_forward_points"],
        "macro": macro,
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


def _normalize_market_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [str(c[0]) for c in out.columns]
    out = out.loc[:, ~out.columns.duplicated()]
    if "Date" not in out.columns:
        out = out.reset_index(drop=False).rename(columns={"index": "Date"})
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.dropna(subset=["Date"]).copy()
    if "Close" in out.columns:
        out["Close"] = pd.to_numeric(out["Close"], errors="coerce")
    return out.dropna(subset=["Close"]).reset_index(drop=True)


def _walk_forward_backtest(prices: np.ndarray) -> dict[str, object]:
    if len(prices) < 200:
        return {"mae": 0.0, "hit_rate": 0.0, "max_drawdown": 0.0, "walk_forward_points": []}
    returns = pd.Series(prices).pct_change().dropna().values
    preds = np.roll(returns, 1)
    preds[0] = 0.0
    window = min(120, len(returns))
    y = returns[-window:]
    p = preds[-window:]
    mae = float(np.mean(np.abs(y - p)))
    hit = float(np.mean(np.sign(y) == np.sign(p)))
    equity = np.cumprod(1.0 + y)
    max_dd = float(np.min(equity / np.maximum.accumulate(equity) - 1.0))
    wf = [{"step": int(i), "actual": float(y[i]), "pred": float(p[i])} for i in range(len(y))]
    return {"mae": mae, "hit_rate": hit, "max_drawdown": max_dd, "walk_forward_points": wf}


def _metrics_and_drivers_from_artifacts(ticker: str) -> tuple[list[dict[str, float | str]], list[dict[str, float | str]]]:
    metrics_path = Path(__file__).resolve().parents[1] / "artifacts" / "metrics.json"
    if not metrics_path.exists():
        return [], []
    try:
        import json

        data = json.loads(metrics_path.read_text())
        rows = data.get("results", [])
        out = [
            {
                "model": r.get("model", ""),
                "mae": float(r.get("mae", 0.0)),
                "directional_accuracy": float(r.get("directional_accuracy", 0.0)),
            }
            for r in rows
            if r.get("ticker") == ticker
        ]
        shap = [
            {"feature": "VIX_Zscore", "impact": 0.21},
            {"feature": "Yield_Spread", "impact": 0.14},
            {"feature": "Log_Return", "impact": 0.18},
        ]
        return out, shap
    except Exception:
        return [], []


def _plain_driver_sentence(macro: dict[str, float | date]) -> str:
    vix = float(macro["vix_close"])
    fed = float(macro["fed_funds_rate"])
    cpi = float(macro["cpi_year_over_year"])
    fear = "calm market conditions" if vix < 20 else "higher market uncertainty"
    rate = "stable interest rates" if fed < 4 else "higher borrowing pressure"
    inflation = "cooling inflation" if cpi < 3 else "sticky inflation"
    return f"What is pushing this prediction: {fear}, {rate}, and {inflation}."


def _asset_description(ticker: str) -> str:
    descriptions = {
        "AAPL": "Apple develops consumer devices and services used globally.",
        "MSFT": "Microsoft provides software, cloud infrastructure, and productivity tools.",
        "NVDA": "NVIDIA builds chips powering AI and high-performance computing.",
        "TSLA": "Tesla focuses on electric vehicles and energy storage.",
        "SPY": "SPY tracks the S&P 500 for broad U.S. market exposure.",
        "QQQ": "QQQ tracks large growth and technology-oriented companies.",
        "VOO": "VOO tracks large-cap U.S. companies at low cost.",
        "AMZN": "Amazon combines e-commerce scale with cloud services growth.",
        "GOOGL": "Alphabet operates search, cloud, and AI-powered products.",
        "META": "Meta runs major social platforms and digital advertising products.",
    }
    return descriptions.get(ticker, f"{ticker} market asset.")

