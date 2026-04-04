from datetime import datetime
import duckdb

import pandas as pd


def get_duckdb_connection(path: str = "data/finvizaard.duckdb") -> duckdb.DuckDBPyConnection:
    return duckdb.connect(path)


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


def insert_price_rows(conn: duckdb.DuckDBPyConnection, df) -> int:
    """
    Expects a pandas DataFrame with columns:
    ticker, ts, open, high, low, close, volume
    """
    conn.register("prices_df", df)
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
    limit: int = 2000,
):
    """
    Returns a pandas dataframe sorted by ts asc.
    """
    return conn.execute(
        """
        SELECT ts, open, high, low, close, volume
        FROM prices
        WHERE ticker = ?
        ORDER BY ts DESC
        LIMIT ?
        """,
        [ticker, int(limit)],
    ).df().sort_values("ts")


def fetch_candles(
    conn: duckdb.DuckDBPyConnection,
    ticker: str,
    *,
    limit: int = 500,
):
    rows = conn.execute(
        """
        SELECT ts, open, high, low, close
        FROM prices
        WHERE ticker = ?
        ORDER BY ts DESC
        LIMIT ?
        """,
        [ticker, int(limit)],
    ).fetchall()

    rows = list(reversed(rows))
    return [
        {
            "time": r[0].strftime("%Y-%m-%d"),
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
        }
        for r in rows
    ]


def upsert_sentiment(conn: duckdb.DuckDBPyConnection, ticker: str, sentiment: dict):
    date_str = datetime.now().strftime("%Y-%m-%d")
    # DuckDB doesn't have native UPSERT, so we delete and insert
    conn.execute(
        "DELETE FROM sentiment_cache WHERE ticker = ? AND date = ?",
        [ticker, date_str]
    )
    conn.execute(
        """
        INSERT INTO sentiment_cache (ticker, date, label, score, top_reason, article_count)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ticker,
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
        [ticker.strip()],
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
