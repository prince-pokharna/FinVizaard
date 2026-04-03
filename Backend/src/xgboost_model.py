from typing import Optional, Tuple, Dict

import pandas as pd
from xgboost import XGBRegressor

from . import database
from .features import make_features, latest_row


_MODEL_CACHE: Dict[str, Tuple[pd.Timestamp, XGBRegressor, list]] = {}


def predict_price(ticker: str, as_of: Optional[str] = None) -> float:
    if not ticker:
        raise ValueError("Ticker is required.")

    model, _, X_latest, _ = get_model_artifacts(ticker, as_of=as_of)
    return float(model.predict(X_latest)[0])


def get_model_artifacts(
    ticker: str,
    *,
    as_of: Optional[str] = None,
    limit: int = 2500,
) -> Tuple[XGBRegressor, list, pd.DataFrame, pd.DataFrame]:
    """
    Returns: (model, feature_cols, X_latest, X_background)
    - X_latest is a 1-row dataframe to explain/predict
    - X_background is a small training sample for SHAP baselines
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

    if len(prices) < 60:
        raise ValueError("Not enough data to train a price model. Ingest more history.")

    last_ts = pd.to_datetime(prices["ts"].max())
    cached = _MODEL_CACHE.get(ticker)
    if cached is None or cached[0] != last_ts:
        model, feature_cols = _train_model(prices)
        _MODEL_CACHE[ticker] = (last_ts, model, feature_cols)
    else:
        model, feature_cols = cached[1], cached[2]

    feats = make_features(prices)
    row = latest_row(feats)
    X_latest = row[feature_cols]

    train_feats = feats.dropna()
    X_bg = train_feats[feature_cols].tail(200) if len(train_feats) > 200 else train_feats[feature_cols]

    return model, feature_cols, X_latest, X_bg


def _train_model(prices: pd.DataFrame) -> Tuple[XGBRegressor, list]:
    feats = make_features(prices)
    feats = feats.dropna()
    if feats.empty:
        raise ValueError("Not enough usable rows to train the price model.")

    feature_cols = [
        "ret_1",
        "ret_5",
        "vol_5",
        "vol_20",
        "ma_5",
        "ma_20",
        "ma_ratio",
        "range",
        "vol_chg",
    ]

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

