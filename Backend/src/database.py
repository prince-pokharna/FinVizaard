from datetime import datetime
import duckdb


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


def get_sentiment(conn: duckdb.DuckDBPyConnection, ticker: str) -> dict:
    date_str = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        """
        SELECT label, score, top_reason, article_count
        FROM sentiment_cache
        WHERE ticker = ? AND date = ?
        """,
        [ticker, date_str]
    ).fetchone()

    if not row:
        return None

    return {
        "label": row[0],
        "score": float(row[1]),
        "top_reason": row[2],
        "article_count": int(row[3])
    }

