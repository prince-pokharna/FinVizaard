from typing import Optional, Dict, Tuple

import pandas as pd
import numpy as np
from hmmlearn.hmm import GaussianHMM

from . import database


def predict_regime(ticker: str, as_of: Optional[str] = None) -> str:
    if not ticker:
        raise ValueError("Ticker is required.")

    ticker = ticker.strip().upper()

    conn = database.get_duckdb_connection()
    try:
        prices = database.fetch_prices_df(conn, ticker, limit=2500)
    finally:
        conn.close()

    if prices.empty:
        raise ValueError(f"No price data found for ticker '{ticker}'. Run /ingest first.")

    if as_of:
        as_of_ts = pd.to_datetime(as_of, errors="coerce")
        if pd.isna(as_of_ts):
            raise ValueError("Invalid 'as_of' date.")
        prices = prices[prices["ts"] <= as_of_ts]

    if len(prices) < 120:
        raise ValueError("Not enough data to detect regimes. Ingest more history.")

    last_ts = pd.to_datetime(prices["ts"].max())
    cached = _HMM_CACHE.get(ticker)
    if cached is None or cached[0] != last_ts:
        model, state_to_label = _train_hmm(prices)
        _HMM_CACHE[ticker] = (last_ts, model, state_to_label)
    else:
        model, state_to_label = cached[1], cached[2]

    X = _make_hmm_features(prices)
    states = model.predict(X)
    latest_state = int(states[-1])
    return state_to_label.get(latest_state, "unknown")


_HMM_CACHE: Dict[str, Tuple[pd.Timestamp, GaussianHMM, Dict[int, str]]] = {}


def _make_hmm_features(prices: pd.DataFrame) -> np.ndarray:
    df = prices.sort_values("ts").copy()
    ret = df["close"].pct_change().fillna(0.0)
    vol = ret.rolling(10).std().fillna(0.0)
    X = np.column_stack([ret.to_numpy(), vol.to_numpy()])
    return X


def _train_hmm(prices: pd.DataFrame) -> Tuple[GaussianHMM, Dict[int, str]]:
    X = _make_hmm_features(prices)
    # HMM can be sensitive; keep it small and stable for hackathon use.
    model = GaussianHMM(
        n_components=3,
        covariance_type="diag",
        n_iter=200,
        random_state=42,
    )
    model.fit(X)

    states = model.predict(X)
    df = prices.sort_values("ts").copy()
    df["ret_1"] = df["close"].pct_change().fillna(0.0)
    df["state"] = states

    means = df.groupby("state")["ret_1"].mean().sort_values()
    # Lowest mean return -> bear, middle -> sideways, highest -> bull
    labels = ["bear", "sideways", "bull"]
    state_to_label = {int(state): labels[i] for i, state in enumerate(means.index.tolist())}
    return model, state_to_label

