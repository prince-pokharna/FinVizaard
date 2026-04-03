import pandas as pd


def make_features(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Input columns: ts, open, high, low, close, volume
    Output: dataframe with engineered features and a 'y' target (next_close).
    """
    df = prices.sort_values("ts").copy()

    df["ret_1"] = df["close"].pct_change()
    df["ret_5"] = df["close"].pct_change(5)
    df["vol_5"] = df["ret_1"].rolling(5).std()
    df["vol_20"] = df["ret_1"].rolling(20).std()
    df["ma_5"] = df["close"].rolling(5).mean()
    df["ma_20"] = df["close"].rolling(20).mean()
    df["ma_ratio"] = df["ma_5"] / df["ma_20"]
    df["range"] = (df["high"] - df["low"]) / df["close"].replace(0, pd.NA)
    df["vol_chg"] = df["volume"].pct_change().replace([pd.NA, float("inf"), float("-inf")], pd.NA)

    df["y"] = df["close"].shift(-1)
    return df


def latest_row(features: pd.DataFrame) -> pd.DataFrame:
    """
    Returns the latest usable feature row (non-null).
    """
    candidate = features.dropna().tail(1)
    if candidate.empty:
        raise ValueError("Not enough data to produce a usable feature row.")
    return candidate

