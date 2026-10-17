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

    if len(prices) < 60:
        raise ValueError("Not enough data to detect regimes. Ingest at least 3-4 months of history.")

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


def get_regime_analysis(ticker: str, as_of: Optional[str] = None, limit: int = 500) -> dict:
    """
    Computes deep HMM market regime analytics including current state,
    posterior probabilities, regime statistics, transition matrix, and timeline.
    """
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

    if len(prices) < 60:
        raise ValueError("Need at least 60 trading days to analyze regimes.")

    last_ts = pd.to_datetime(prices["ts"].max())
    cached = _HMM_CACHE.get(ticker)
    if cached is None or cached[0] != last_ts:
        model, state_to_label = _train_hmm(prices)
        _HMM_CACHE[ticker] = (last_ts, model, state_to_label)
    else:
        model, state_to_label = cached[1], cached[2]

    X = _make_hmm_features(prices)
    states = model.predict(X)
    probs = model.predict_proba(X)

    df = prices.sort_values("ts").copy()
    df["ret_1"] = df["close"].pct_change().fillna(0.0)
    df["state"] = states
    df["regime"] = [state_to_label.get(int(s), "unknown") for s in states]

    latest_state = int(states[-1])
    current_regime = state_to_label.get(latest_state, "unknown")
    latest_probs = probs[-1]

    regime_probs = {
        state_to_label[s]: round(float(latest_probs[s]) * 100.0, 1)
        for s in state_to_label
    }

    # State distribution
    total_days = len(df)
    counts = df["regime"].value_counts().to_dict()
    distribution = {
        k: round((counts.get(k, 0) / total_days) * 100.0, 1)
        for k in ["bull", "sideways", "bear"]
    }

    # Regime performance statistics
    stats = {}
    for r in ["bull", "sideways", "bear"]:
        sub = df[df["regime"] == r]
        if not sub.empty:
            mean_ret = float(sub["ret_1"].mean()) * 100.0
            ann_vol = float(sub["ret_1"].std() * np.sqrt(252)) * 100.0 if len(sub) > 1 else 0.0
            stats[r] = {
                "days": len(sub),
                "mean_daily_return_pct": round(mean_ret, 3),
                "annualized_volatility_pct": round(ann_vol, 2),
            }
        else:
            stats[r] = {"days": 0, "mean_daily_return_pct": 0.0, "annualized_volatility_pct": 0.0}

    # Transition matrix labeled
    trans_matrix = {}
    if hasattr(model, "transmat_"):
        for i, row in enumerate(model.transmat_):
            from_label = state_to_label.get(i, f"state_{i}")
            trans_matrix[from_label] = {
                state_to_label.get(j, f"state_{j}"): round(float(p) * 100.0, 1)
                for j, p in enumerate(row)
            }

    # Timeline for charting (last 'limit' points)
    recent = df.tail(limit)
    timeline = [
        {
            "time": pd.Timestamp(r["ts"]).strftime("%Y-%m-%d"),
            "regime": r["regime"],
            "close": round(float(r["close"]), 2),
        }
        for _, r in recent.iterrows()
    ]

    return {
        "ticker": ticker,
        "current_regime": current_regime,
        "regime_probabilities": regime_probs,
        "distribution": distribution,
        "stats": stats,
        "transition_matrix": trans_matrix,
        "timeline": timeline,
    }


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

