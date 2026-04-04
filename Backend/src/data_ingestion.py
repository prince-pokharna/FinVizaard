from typing import Iterable, List, Tuple
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from . import database


def ingest_tickers(tickers: Iterable[str], start_date: str, end_date: str) -> int:
    """
    Download OHLCV data for tickers between dates and return row count.
    """
    tickers_list: List[str] = [t.strip().upper() for t in tickers if t and t.strip()]
    if not tickers_list:
        raise ValueError("At least one ticker is required.")

    start_ts = pd.to_datetime(start_date, errors="coerce")
    end_ts = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(start_ts) or pd.isna(end_ts):
        raise ValueError("Invalid start_date or end_date.")
    if start_ts >= end_ts:
        raise ValueError("start_date must be earlier than end_date.")

    data, used_synthetic = _download_prices_with_fallback(tickers_list, start_date, end_date)

    prices_df = _normalize_yfinance_prices(data, tickers_list)
    if prices_df.empty:
        raise ValueError("No normalized price rows produced.")

    Path("data").mkdir(parents=True, exist_ok=True)
    conn = database.get_duckdb_connection()
    try:
        database.init_duckdb_schema(conn)
        inserted = database.insert_price_rows(conn, prices_df)
        database.set_ingest_synthetic_flags(conn, tickers_list, 1 if used_synthetic else 0)
    finally:
        conn.close()

    return int(inserted)


def _download_prices_with_fallback(
    tickers: List[str], start_date: str, end_date: str
) -> Tuple[pd.DataFrame, bool]:
    """
    Try Yahoo Finance first. If unavailable/rate-limited, generate deterministic
    synthetic OHLCV series so the full app workflow remains usable.

    Returns (ohlcv_dataframe, used_synthetic).
    """
    try:
        data = yf.download(
            tickers=" ".join(tickers),
            start=start_date,
            end=end_date,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if not data.empty:
            return data, False
    except Exception:
        # Fall back below.
        pass

    return _build_synthetic_market_data(tickers, start_date, end_date), True


def _build_synthetic_market_data(tickers: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    start_ts = pd.to_datetime(start_date).normalize()
    end_ts = pd.to_datetime(end_date).normalize()
    dates = pd.bdate_range(start=start_ts, end=end_ts - pd.Timedelta(days=1))
    if len(dates) < 40:
        raise ValueError("Date range is too short. Please select at least 2 months of data.")

    frames = []
    for ticker in tickers:
        seed = int(np.frombuffer(ticker.encode("utf-8"), dtype=np.uint8).sum())
        rng = np.random.default_rng(seed)

        daily_ret = rng.normal(loc=0.0004, scale=0.02, size=len(dates))
        close = 100.0 * np.cumprod(1.0 + daily_ret)
        open_ = close * (1.0 + rng.normal(0.0, 0.004, size=len(dates)))
        high = np.maximum(open_, close) * (1.0 + rng.uniform(0.0005, 0.015, size=len(dates)))
        low = np.minimum(open_, close) * (1.0 - rng.uniform(0.0005, 0.015, size=len(dates)))
        volume = rng.integers(800_000, 12_000_000, size=len(dates)).astype(float)

        df = pd.DataFrame(
            {
                "Date": dates,
                "Open": open_,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": volume,
            }
        )
        df["Ticker"] = ticker
        frames.append(df)

    if len(frames) == 1:
        return frames[0].set_index("Date")[["Open", "High", "Low", "Close", "Volume"]]

    combined = pd.concat(frames, ignore_index=True)
    return (
        combined.set_index(["Date", "Ticker"])[["Open", "High", "Low", "Close", "Volume"]]
        .unstack("Ticker")
        .sort_index()
    )


def _normalize_yfinance_prices(data: pd.DataFrame, tickers: List[str]) -> pd.DataFrame:
    """
    Returns a dataframe with columns:
    ticker, ts, open, high, low, close, volume
    """
    if isinstance(data.columns, pd.MultiIndex):
        # Columns: field x ticker (or ticker x field depending on yfinance),
        # so convert to long format.
        stacked = data.stack(level=1).reset_index()
        stacked = stacked.rename(columns={"Date": "ts", "Datetime": "ts"})

        # When stacked, the ticker column name varies; detect it.
        ticker_col = None
        for candidate in ("Ticker", "Symbols", "symbol", "ticker"):
            if candidate in stacked.columns:
                ticker_col = candidate
                break
        if ticker_col is None:
            # The second index column after ts is usually the ticker
            idx_cols = [c for c in stacked.columns if c in ("ts", "Date", "Datetime")]
            other = [c for c in stacked.columns if c not in idx_cols and c not in ("Open", "High", "Low", "Close", "Volume")]
            if other:
                ticker_col = other[0]

        if ticker_col is None or ticker_col not in stacked.columns:
            raise ValueError("Could not detect ticker column after stacking yfinance data.")

        df = stacked.rename(
            columns={
                ticker_col: "ticker",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
    else:
        # Single ticker: index is ts, columns are OHLCV
        if len(tickers) != 1:
            raise ValueError("Expected multi-ticker data but received single-index columns.")
        df = data.reset_index().rename(
            columns={
                "Date": "ts",
                "Datetime": "ts",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        df["ticker"] = tickers[0]

    needed = ["ticker", "ts", "open", "high", "low", "close", "volume"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns after normalization: {missing}")

    out = df[needed].copy()
    out["ticker"] = out["ticker"].astype(str).str.upper()
    out["ts"] = pd.to_datetime(out["ts"], utc=False, errors="coerce")
    out = out.dropna(subset=["ts", "close"])
    out = out.sort_values(["ticker", "ts"])
    return out

