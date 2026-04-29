from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.preprocessing import StandardScaler

from .config import DataConfig, PathsConfig

MAX_CACHE_AGE_HOURS = 24


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


def _fetch_fred_series(series_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        df = pd.read_csv(url)
    except Exception:
        return pd.DataFrame()
    if df.empty or len(df.columns) < 2:
        return pd.DataFrame()
    df.columns = ["Date", "Value"]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    out = df[(df["Date"] >= start) & (df["Date"] <= end)].dropna().reset_index(drop=True)
    return out


def _sentiment_proxy_from_returns(log_returns: pd.Series) -> pd.Series:
    # Placeholder until FinBERT headline pipeline is wired in.
    daily_sign = np.sign(log_returns.fillna(0))
    return daily_sign.rolling(5).mean().fillna(0)


def _earnings_next_5d_flag(dates: pd.Series, ticker: str) -> pd.Series:
    try:
        earnings = yf.Ticker(ticker).get_earnings_dates(limit=40)
        if earnings is None or len(earnings) == 0:
            return pd.Series(np.zeros(len(dates), dtype=float))
        earnings_dates = pd.to_datetime(pd.Index(earnings.index), errors="coerce").dropna().normalize().to_list()
    except Exception:
        return pd.Series(np.zeros(len(dates), dtype=float))

    normalized_dates = pd.to_datetime(dates, errors="coerce").dt.normalize()
    flags: list[float] = []
    for d in normalized_dates:
        if pd.isna(d):
            flags.append(0.0)
            continue
        window_end = d + pd.Timedelta(days=5)
        has_earnings = any((e >= d) and (e <= window_end) for e in earnings_dates)
        flags.append(1.0 if has_earnings else 0.0)
    return pd.Series(flags, index=dates.index)


def _fetch_macro_features(
    start_date: str,
    end_date: str,
    cache_dir: Path
) -> pd.DataFrame:
    macro_cache = cache_dir / f"macro_{start_date}_{end_date}.csv"
    required_columns = {"Date", "VIX_Zscore", "Yield_Spread", "DXY", "FedFunds", "CPI_MoM"}

    if macro_cache.exists():
        age = datetime.datetime.now() - datetime.datetime.fromtimestamp(macro_cache.stat().st_mtime)
        if age.total_seconds() < 24 * 3600:
            cached = pd.read_csv(macro_cache, parse_dates=["Date"])
            if required_columns.issubset(set(cached.columns)):
                return cached
            print("Macro cache missing required columns, re-fetching...")
        print("Cache expired for macro data, re-fetching...")

    macro_tickers = {
        "^VIX": "VIX",
        "^TNX": "Yield_10Y",
        "^IRX": "Yield_3M",
        "DX-Y.NYB": "DXY",
    }
    frames = []
    for ticker, col in macro_tickers.items():
        try:
            df = yf.download(
                ticker, start=start_date, end=end_date,
                auto_adjust=False, progress=False
            ).reset_index()
            df = _normalize_raw_frame(df)
            df = df[["Date", "Close"]].rename(columns={"Close": col})
            frames.append(df)
        except Exception:
            pass

    if not frames:
        return pd.DataFrame()

    macro = frames[0]
    for f in frames[1:]:
        macro = macro.merge(f, on="Date", how="outer")
    macro = macro.sort_values("Date").ffill().bfill()

    if "Yield_10Y" in macro.columns and "Yield_3M" in macro.columns:
        macro["Yield_Spread"] = macro["Yield_10Y"] - macro["Yield_3M"]

    if "VIX" in macro.columns:
        macro["VIX_Zscore"] = (
            (macro["VIX"] - macro["VIX"].rolling(252).mean()) /
            macro["VIX"].rolling(252).std()
        ).fillna(0)

    fed = _fetch_fred_series("FEDFUNDS", start_date, end_date)
    if not fed.empty:
        fed = fed.rename(columns={"Value": "FedFunds"})
        macro = macro.merge(fed[["Date", "FedFunds"]], on="Date", how="left")
    else:
        macro["FedFunds"] = np.nan

    cpi = _fetch_fred_series("CPIAUCSL", start_date, end_date)
    if not cpi.empty:
        cpi = cpi.rename(columns={"Value": "CPI"})
        cpi["CPI_MoM"] = cpi["CPI"].pct_change().fillna(0)
        macro = macro.merge(cpi[["Date", "CPI_MoM"]], on="Date", how="left")
    else:
        macro["CPI_MoM"] = np.nan

    macro[["FedFunds", "CPI_MoM"]] = macro[["FedFunds", "CPI_MoM"]].ffill().bfill().fillna(0)

    macro.to_csv(macro_cache, index=False)
    return macro


def _engineer_features(frame: pd.DataFrame, macro_df: pd.DataFrame | None = None) -> pd.DataFrame:
    df = frame.copy()
    if "Date" not in df.columns:
        df = df.reset_index(drop=False).rename(columns={"index": "Date"})
    df["Log_Return"] = np.log(df["Close"] / df["Close"].shift(1))
    df["SMA_10"] = df["Close"].rolling(10).mean()
    df["SMA_30"] = df["Close"].rolling(30).mean()
    df["EMA_12"] = df["Close"].ewm(span=12, adjust=False).mean()
    df["RSI_14"] = _compute_rsi(df["Close"], period=14)
    df["Daily_Return"] = df["Close"].pct_change()
    df["Volatility_10"] = df["Daily_Return"].rolling(10).std()
    df["Log_Return"] = np.log(df["Close"] / df["Close"].shift(1)).fillna(0)
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
    today = datetime.date.today().strftime("%Y-%m-%d")
    effective_end = today if data_cfg.end_date < today else data_cfg.end_date
    cache_file = cache_dir / f"{ticker}_{data_cfg.start_date}_{effective_end}.csv"
    if cache_file.exists():
        age = datetime.datetime.now() - datetime.datetime.fromtimestamp(cache_file.stat().st_mtime)
        if age.total_seconds() < MAX_CACHE_AGE_HOURS * 3600:
            cached = pd.read_csv(cache_file)
            return _normalize_raw_frame(cached)
        print(f"Cache expired for {ticker}, re-fetching...")

    df = yf.download(
        ticker,
        start=data_cfg.start_date,
        end=effective_end,
        auto_adjust=False,
        progress=False,
    ).reset_index()
    df = _normalize_raw_frame(df)
    if df.empty:
        raise RuntimeError(f"No data returned for {ticker}")
    df.to_csv(cache_file, index=False)
    return df


def reconstruct_prices(
    last_known_price: float,
    predicted_log_returns: np.ndarray
) -> np.ndarray:
    """Convert predicted log returns back to price levels for display."""
    prices = [last_known_price]
    for r in predicted_log_returns:
        prices.append(prices[-1] * np.exp(r))
    return np.array(prices[1:])


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
    macro = _fetch_macro_features(data_cfg.start_date, data_cfg.end_date, paths_cfg.data_cache_dir)
    if not macro.empty:
        for col in ["VIX_Zscore", "Yield_Spread", "DXY", "FedFunds", "CPI_MoM"]:
            if col not in macro.columns:
                macro[col] = 0.0
        fe = fe.merge(
            macro[["Date", "VIX_Zscore", "Yield_Spread", "DXY", "FedFunds", "CPI_MoM"]],
            on="Date", how="left"
        )
        fe[["VIX_Zscore", "Yield_Spread", "DXY", "FedFunds", "CPI_MoM"]] = (
            fe[["VIX_Zscore", "Yield_Spread", "DXY", "FedFunds", "CPI_MoM"]].ffill().fillna(0)
        )

    fe["Sentiment_5D"] = _sentiment_proxy_from_returns(fe["Log_Return"])
    fe["Earnings_Next5D"] = _earnings_next_5d_flag(fe["Date"], ticker=ticker)
    if "SPY" in data_cfg.tickers:
        spy_raw = _download_or_load_cache("SPY", data_cfg=data_cfg, cache_dir=paths_cfg.data_cache_dir)
        spy_frame = _engineer_features(spy_raw)[["Date", "Log_Return"]].rename(columns={"Log_Return": "SPY_Log_Return"})
        fe = fe.merge(spy_frame, on="Date", how="left")
        fe["Corr_SPY_20"] = fe["Log_Return"].rolling(20).corr(fe["SPY_Log_Return"]).fillna(0)
        fe = fe.drop(columns=["SPY_Log_Return"])
    else:
        fe["Corr_SPY_20"] = 0.0

    feature_store_file = paths_cfg.feature_store_dir / f"{ticker}_features.csv"
    fe.to_csv(feature_store_file, index=False)

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
