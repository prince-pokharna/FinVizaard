from typing import Optional, Tuple, Dict

import pandas as pd
from xgboost import XGBRegressor

from . import database
from .features import make_features, latest_row


FEATURE_COLS = [
    "ret_1",
    "ret_5",
    "vol_5",
    "vol_20",
    "ma_5",
    "ma_20",
    "ma_ratio",
    "range",
    "vol_chg",
    "vix_close",
    "vix_change",
    "sentiment_score",
    "ma_50",
    "price_vs_ma50",
    "vol_regime",
]

FEATURE_SCHEMA_VERSION = "macro-sentiment-v1"

_MODEL_CACHE: Dict[str, Tuple[pd.Timestamp, XGBRegressor, list, str]] = {}


def predict_price(ticker: str, as_of: Optional[str] = None) -> float:
    if not ticker:
        raise ValueError("Ticker is required.")

    model, _, X_latest, _, _ = get_model_artifacts(ticker, as_of=as_of)
    return float(model.predict(X_latest)[0])


def get_model_artifacts(
    ticker: str,
    *,
    as_of: Optional[str] = None,
    limit: int = 2500,
) -> Tuple[XGBRegressor, list, pd.DataFrame, pd.DataFrame, float]:
    """
    Returns: (model, feature_cols, X_latest, X_background, last_close)
    - X_latest is a 1-row dataframe to explain/predict
    - X_background is a small training sample for SHAP baselines
    - last_close is the latest observed close in the price window used
    """
    if not ticker:
        raise ValueError("Ticker is required.")

    ticker = ticker.strip().upper()

    conn = database.get_duckdb_connection()
    try:
        prices = database.fetch_prices_df(conn, ticker, limit=int(limit))
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
        raise ValueError("Not enough data to train a price model. Ingest more history.")

    last_ts = pd.to_datetime(prices["ts"].max())
    cached = _MODEL_CACHE.get(ticker)
    if (
        cached is None
        or cached[0] != last_ts
        or cached[3] != FEATURE_SCHEMA_VERSION
    ):
        model, feature_cols = _train_model(prices, ticker)
        _MODEL_CACHE[ticker] = (last_ts, model, feature_cols, FEATURE_SCHEMA_VERSION)
    else:
        model, feature_cols = cached[1], cached[2]

    feats = make_features(prices, ticker)
    row = latest_row(feats)
    X_latest = row[feature_cols]

    train_feats = feats.dropna()
    X_bg = train_feats[feature_cols].tail(200) if len(train_feats) > 200 else train_feats[feature_cols]

    last_close = float(prices.sort_values("ts")["close"].iloc[-1])

    return model, feature_cols, X_latest, X_bg, last_close


def _train_model(prices: pd.DataFrame, ticker: str) -> Tuple[XGBRegressor, list]:
    feats = make_features(prices, ticker)
    feats = feats.dropna()
    if feats.empty:
        raise ValueError("Not enough usable rows to train the price model.")

    feature_cols = list(FEATURE_COLS)

    X = feats[feature_cols]
    y = feats["y"]

    model = XGBRegressor(
        n_estimators=250,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        objective="reg:squarederror",
        random_state=42,
        n_jobs=0,
    )
    model.fit(X, y)
    return model, feature_cols
