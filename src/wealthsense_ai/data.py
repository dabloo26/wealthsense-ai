from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.preprocessing import StandardScaler

from .config import DataConfig, PathsConfig


@dataclass(slots=True)
class PreparedTickerData:
    ticker: str
    train_x: np.ndarray
    train_y: np.ndarray
    val_x: np.ndarray
    val_y: np.ndarray
    test_x: np.ndarray
    test_y: np.ndarray
    test_dates: pd.Series
    scaler: StandardScaler
    full_frame: pd.DataFrame


def _compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.where(delta > 0.0, 0.0)
    losses = (-delta).where(delta < 0.0, 0.0)
    avg_gain = gains.rolling(period).mean()
    avg_loss = losses.rolling(period).mean().replace(0.0, 1e-10)
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _engineer_features(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    if "Date" not in df.columns:
        df = df.reset_index(drop=False).rename(columns={"index": "Date"})
    df["SMA_10"] = df["Close"].rolling(10).mean()
    df["SMA_30"] = df["Close"].rolling(30).mean()
    df["EMA_12"] = df["Close"].ewm(span=12, adjust=False).mean()
    df["RSI_14"] = _compute_rsi(df["Close"], period=14)
    df["Daily_Return"] = df["Close"].pct_change()
    df["Volatility_10"] = df["Daily_Return"].rolling(10).std()
    out = df.dropna().copy()
    out["Date"] = pd.to_datetime(out["Date"])
    out = out.loc[:, ~out.columns.duplicated()]
    return out.reset_index(drop=True)


def _build_sequences(
    features: np.ndarray,
    targets: np.ndarray,
    dates: pd.Series,
    seq_len: int,
) -> tuple[np.ndarray, np.ndarray, pd.Series]:
    x_rows: list[np.ndarray] = []
    y_rows: list[float] = []
    d_rows: list[pd.Timestamp] = []
    for i in range(seq_len, len(features)):
        x_rows.append(features[i - seq_len : i])
        y_rows.append(float(targets[i]))
        d_rows.append(dates.iloc[i])
    return np.array(x_rows), np.array(y_rows), pd.Series(d_rows)


def _download_or_load_cache(ticker: str, data_cfg: DataConfig, cache_dir: Path) -> pd.DataFrame:
    cache_file = cache_dir / f"{ticker}_{data_cfg.start_date}_{data_cfg.end_date}.csv"
    if cache_file.exists():
        cached = pd.read_csv(cache_file)
        return _normalize_raw_frame(cached)

    df = yf.download(
        ticker,
        start=data_cfg.start_date,
        end=data_cfg.end_date,
        auto_adjust=False,
        progress=False,
    ).reset_index()
    df = _normalize_raw_frame(df)
    if df.empty:
        raise RuntimeError(f"No data returned for {ticker}")
    df.to_csv(cache_file, index=False)
    return df


def _normalize_raw_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [str(c[0]) for c in out.columns]

    out = out.loc[:, ~out.columns.duplicated()]
    if "Date" not in out.columns:
        out = out.reset_index(drop=False).rename(columns={"index": "Date"})

    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.dropna(subset=["Date"]).copy()

    for col in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    # Handles cached files that may contain a second row with ticker labels.
    out = out.dropna(subset=["Close"]).reset_index(drop=True)
    return out


def prepare_ticker_data(data_cfg: DataConfig, paths_cfg: PathsConfig, ticker: str) -> PreparedTickerData:
    raw = _download_or_load_cache(ticker=ticker, data_cfg=data_cfg, cache_dir=paths_cfg.data_cache_dir)
    fe = _engineer_features(raw)

    feature_values = fe[data_cfg.feature_columns].astype(float).values
    target_values = fe[data_cfg.target_column].astype(float).values
    dates = fe["Date"]

    scaler = StandardScaler()
    train_mask = dates.dt.year <= 2021
    scaler.fit(feature_values[train_mask.values])
    scaled_features = scaler.transform(feature_values)

    x_all, y_all, d_all = _build_sequences(
        features=scaled_features,
        targets=target_values,
        dates=dates,
        seq_len=data_cfg.sequence_length,
    )
    year_all = d_all.dt.year
    train_sel = year_all <= 2021
    val_sel = year_all == 2022
    test_sel = year_all == 2023

    return PreparedTickerData(
        ticker=ticker,
        train_x=x_all[train_sel.values],
        train_y=y_all[train_sel.values],
        val_x=x_all[val_sel.values],
        val_y=y_all[val_sel.values],
        test_x=x_all[test_sel.values],
        test_y=y_all[test_sel.values],
        test_dates=d_all[test_sel.values].reset_index(drop=True),
        scaler=scaler,
        full_frame=fe,
    )
