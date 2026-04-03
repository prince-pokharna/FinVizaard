from typing import Iterable, List
from pathlib import Path

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

    data = yf.download(tickers=" ".join(tickers_list), start=start_date, end=end_date, auto_adjust=True)

    if data.empty:
        raise ValueError("No data returned from yfinance for the given parameters.")

    prices_df = _normalize_yfinance_prices(data, tickers_list)
    if prices_df.empty:
        raise ValueError("No normalized price rows produced.")

    Path("data").mkdir(parents=True, exist_ok=True)
    conn = database.get_duckdb_connection()
    try:
        database.init_duckdb_schema(conn)
        inserted = database.insert_price_rows(conn, prices_df)
    finally:
        conn.close()

    return int(inserted)


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

