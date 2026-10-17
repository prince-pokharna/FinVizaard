from datetime import datetime
from pathlib import Path
import duckdb
import pandas as pd


def get_duckdb_connection(path: str = "data/finvizaard.duckdb") -> duckdb.DuckDBPyConnection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(path)
    init_duckdb_schema(conn)
    return conn


def init_duckdb_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS prices (
            ticker TEXT,
            ts TIMESTAMP,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prices_ticker_ts ON prices(ticker, ts)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sentiment_cache (
            ticker TEXT,
            date TEXT,
            label TEXT,
            score REAL,
            top_reason TEXT,
            article_count INTEGER
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_ticker_date ON sentiment_cache(ticker, date)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ingest_meta (
            ticker TEXT PRIMARY KEY,
            synthetic INTEGER NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS macro_cache (
            indicator TEXT,
            date TEXT,
            value DOUBLE,
            PRIMARY KEY (indicator, date)
        )
        """
    )


def insert_price_rows(conn: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
    """
    Expects a pandas DataFrame with columns:
    ticker, ts, open, high, low, close, volume.
    Deduplicates and removes overlapping timestamps before inserting.
    """
    if df.empty:
        return 0

    clean_df = df.dropna(subset=["ts", "close"]).copy()
    clean_df["ticker"] = clean_df["ticker"].astype(str).str.upper()
    clean_df = clean_df.drop_duplicates(subset=["ticker", "ts"])

    for ticker, group in clean_df.groupby("ticker"):
        min_ts = group["ts"].min()
        max_ts = group["ts"].max()
        conn.execute(
            "DELETE FROM prices WHERE UPPER(ticker) = UPPER(?) AND ts >= ? AND ts <= ?",
            [ticker, min_ts, max_ts],
        )

    conn.register("prices_df", clean_df)
    conn.execute(
        """
        INSERT INTO prices
        SELECT ticker, ts, open, high, low, close, volume
        FROM prices_df
        """
    )
    return int(conn.execute("SELECT COUNT(*) FROM prices_df").fetchone()[0])


def fetch_prices_df(
    conn: duckdb.DuckDBPyConnection,
    ticker: str,
    *,
    limit: int = 2500,
) -> pd.DataFrame:
    """
    Returns a pandas dataframe sorted by ts asc, guaranteed deduplicated.
    """
    return conn.execute(
        """
        SELECT DISTINCT ON (ts) ts, open, high, low, close, volume
        FROM prices
        WHERE UPPER(ticker) = UPPER(?)
        ORDER BY ts DESC, volume DESC
        LIMIT ?
        """,
        [ticker.strip().upper(), int(limit)],
    ).df().sort_values("ts")


def fetch_candles(
    conn: duckdb.DuckDBPyConnection,
    ticker: str,
    *,
    limit: int = 500,
):
    rows = conn.execute(
        """
        SELECT DISTINCT ON (ts) ts, open, high, low, close, volume
        FROM prices
        WHERE UPPER(ticker) = UPPER(?)
        ORDER BY ts DESC, volume DESC
        LIMIT ?
        """,
        [ticker.strip().upper(), int(limit)],
    ).fetchall()

    rows = list(reversed(rows))
    return [
        {
            "time": r[0].strftime("%Y-%m-%d"),
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]) if len(r) > 5 and r[5] is not None else 0.0,
        }
        for r in rows
    ]


def upsert_sentiment(conn: duckdb.DuckDBPyConnection, ticker: str, sentiment: dict):
    date_str = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        "DELETE FROM sentiment_cache WHERE UPPER(ticker) = UPPER(?) AND date = ?",
        [ticker.strip().upper(), date_str]
    )
    conn.execute(
        """
        INSERT INTO sentiment_cache (ticker, date, label, score, top_reason, article_count)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ticker.strip().upper(),
            date_str,
            sentiment.get("label", "neutral"),
            float(sentiment.get("score", 0.0)),
            sentiment.get("top_reason", ""),
            int(sentiment.get("article_count", 0))
        ]
    )


def get_sentiment(conn: duckdb.DuckDBPyConnection, ticker: str, as_of_ts) -> float:
    """
    Nearest cached sentiment score for this ticker to as_of_ts (by calendar day).
    Returns 0.0 if no rows exist in sentiment_cache.
    """
    target = pd.Timestamp(as_of_ts).normalize()
    rows = conn.execute(
        """
        SELECT date, score
        FROM sentiment_cache
        WHERE UPPER(ticker) = UPPER(?)
        """,
        [ticker.strip().upper()],
    ).fetchall()
    if not rows:
        return 0.0

    best_score = 0.0
    best_days = None
    for date_str, score in rows:
        d = pd.to_datetime(date_str, errors="coerce")
        if pd.isna(d):
            continue
        d = d.normalize()
        days = abs((d - target).days)
        if best_days is None or days < best_days:
            best_days = days
            best_score = float(score)
    return best_score


def set_ingest_synthetic_flags(conn: duckdb.DuckDBPyConnection, tickers: list[str], synthetic: int) -> None:
    """Mark whether the latest ingest for each ticker used synthetic OHLCV (1) or Yahoo (0)."""
    t = [x.strip().upper() for x in tickers if x and str(x).strip()]
    for sym in t:
        conn.execute("DELETE FROM ingest_meta WHERE ticker = ?", [sym])
        conn.execute(
            "INSERT INTO ingest_meta (ticker, synthetic) VALUES (?, ?)",
            [sym, int(synthetic)],
        )


def get_cached_macro(conn: duckdb.DuckDBPyConnection, indicator: str, start_date: str, end_date: str) -> pd.Series:
    rows = conn.execute(
        """
        SELECT date, value
        FROM macro_cache
        WHERE UPPER(indicator) = UPPER(?) AND date >= ? AND date <= ?
        ORDER BY date ASC
        """,
        [indicator.strip().upper(), start_date, end_date],
    ).fetchall()
    if not rows:
        return pd.Series(dtype=float, name=indicator)
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.Series([float(r[1]) for r in rows], index=idx, name=indicator)


def store_cached_macro(conn: duckdb.DuckDBPyConnection, indicator: str, series: pd.Series) -> None:
    if series.empty:
        return
    for date_val, val in series.items():
        if pd.isna(val):
            continue
        d_str = pd.Timestamp(date_val).strftime("%Y-%m-%d")
        conn.execute(
            "DELETE FROM macro_cache WHERE indicator = ? AND date = ?",
            [indicator.upper(), d_str],
        )
        conn.execute(
            "INSERT INTO macro_cache (indicator, date, value) VALUES (?, ?, ?)",
            [indicator.upper(), d_str, float(val)],
        )


def get_stored_tickers(conn: duckdb.DuckDBPyConnection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM prices ORDER BY ticker"
    ).fetchall()
    return [r[0] for r in rows]

