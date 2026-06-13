import numpy as np
import pandas as pd
import yfinance as yf

from . import database


def get_vix_features(start_date: str, end_date: str) -> pd.Series:
    """
    Download ^VIX close for the date range from Yahoo Finance.

    Parameters:
    -----------
    start_date : str
        Start date in 'YYYY-MM-DD' format.
    end_date : str
        End date in 'YYYY-MM-DD' format.

    Returns:
    --------
    pd.Series
        Series named 'vix_close' indexed by calendar date (normalized).
        On failure, returns zeros on the business-day index spanning the date range.
    """
    start_ts = pd.to_datetime(start_date, errors="coerce").normalize()
    end_ts = pd.to_datetime(end_date, errors="coerce").normalize()
    if pd.isna(start_ts) or pd.isna(end_ts):
        idx = pd.DatetimeIndex([])
        return pd.Series(dtype=float, name="vix_close", index=idx)

    bdays = pd.bdate_range(start=start_ts, end=end_ts - pd.Timedelta(days=1))
    zero_series = pd.Series(0.0, index=bdays.normalize(), name="vix_close")

    try:
        data = yf.download(
            "^VIX",
            start=start_date,
            end=end_date,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if data is None or data.empty or "Close" not in data.columns:
            return zero_series

        s = data["Close"].copy()
        s.index = pd.to_datetime(s.index, errors="coerce").normalize()
        s = s[~s.index.duplicated(keep="last")]
        s.name = "vix_close"
        return s
    except Exception:
        return zero_series


def _use_dummy_macro_sentiment(conn, ticker: str) -> bool:
    row = conn.execute(
        "SELECT synthetic FROM ingest_meta WHERE ticker = ?",
        [ticker.strip().upper()],
    ).fetchone()
    return bool(row and int(row[0]) == 1)


def make_features(prices: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Calculates engineered technical features and targets for a given stock ticker.

    Parameters:
    -----------
    prices : pd.DataFrame
        DataFrame containing historical price data with columns:
        ts, open, high, low, close, volume.
    ticker : str
        The stock ticker symbol.

    Returns:
    --------
    pd.DataFrame
        A DataFrame with original columns and added features:
        ret_1, ret_5, vol_5, vol_20, ma_5, ma_20, ma_50, ma_ratio,
        price_vs_ma50, range, vol_chg, vol_regime, vix_close,
        vix_change, sentiment_score, and the target variable 'y'.
    """
    if not ticker or not str(ticker).strip():
        raise ValueError("Ticker is required for feature engineering.")

    ticker = ticker.strip().upper()
    df = prices.sort_values("ts").copy()

    df["ret_1"] = df["close"].pct_change()
    df["ret_5"] = df["close"].pct_change(5)
    df["vol_5"] = df["ret_1"].rolling(5).std()
    df["vol_20"] = df["ret_1"].rolling(20).std()
    df["ma_5"] = df["close"].rolling(5).mean()
    df["ma_20"] = df["close"].rolling(20).mean()
    df["ma_50"] = df["close"].rolling(50).mean()
    df["ma_ratio"] = df["ma_5"] / df["ma_20"].replace(0, np.nan)
    df["price_vs_ma50"] = df["close"] / df["ma_50"].replace(0, np.nan)
    df["range"] = (df["high"] - df["low"]) / df["close"].replace(0, np.nan)
    df["vol_chg"] = df["volume"].pct_change().replace([pd.NA, float("inf"), float("-inf")], np.nan)

    vol20_mean60 = df["vol_20"].rolling(60).mean()
    df["vol_regime"] = np.where(
        vol20_mean60.isna(),
        0.0,
        (df["vol_20"] > 1.5 * vol20_mean60).astype(float),
    )

    dmin = df["ts"].min()
    dmax = df["ts"].max()
    start_s = pd.Timestamp(dmin).strftime("%Y-%m-%d")
    end_s = (pd.Timestamp(dmax) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    conn = database.get_duckdb_connection()
    try:
        dummy = _use_dummy_macro_sentiment(conn, ticker)
        if dummy:
            df["vix_close"] = 20.0
            df["vix_change"] = 0.0
            df["sentiment_score"] = 0.0
        else:
            vix = get_vix_features(start_s, end_s)
            vix = vix.copy()
            vix.index = pd.to_datetime(vix.index).normalize()
            idx = pd.to_datetime(df["ts"]).dt.normalize()
            aligned = vix.reindex(idx)
            aligned = aligned.ffill().bfill()
            if aligned.isna().all():
                aligned = pd.Series(0.0, index=df.index)
            else:
                aligned = aligned.fillna(0.0)
            df["vix_close"] = aligned.astype(float).values
            df["vix_change"] = (
                df["vix_close"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
            )
            df["sentiment_score"] = [
                float(database.get_sentiment(conn, ticker, ts)) for ts in df["ts"]
            ]
    finally:
        conn.close()

    df["y"] = df["close"].shift(-1)
    return df


def latest_row(features: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts the latest complete feature record from the features DataFrame.

    Parameters:
    -----------
    features : pd.DataFrame
        DataFrame with calculated technical features.

    Returns:
    --------
    pd.DataFrame
        A single-row DataFrame containing the latest non-null features.
    """
    candidate = features.dropna().tail(1)
    if candidate.empty:
        raise ValueError("Not enough data to produce a usable feature row.")
    return candidate
