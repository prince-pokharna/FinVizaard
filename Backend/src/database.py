import duckdb


def get_duckdb_connection(path: str = "data/clearalpha.duckdb") -> duckdb.DuckDBPyConnection:
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

