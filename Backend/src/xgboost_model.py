from typing import Optional, Tuple, Dict

import numpy as np
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

    if len(prices) < 60:
        raise ValueError("Not enough data to train a price model. Ingest at least 3-4 months of history.")

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
    row = latest_row(feats, feature_cols)
    X_latest = row[feature_cols]

    train_feats = feats.dropna()
    X_bg = train_feats[feature_cols].tail(200) if len(train_feats) > 200 else train_feats[feature_cols]

    last_close = float(prices.sort_values("ts")["close"].iloc[-1])

    return model, feature_cols, X_latest, X_bg, last_close


def get_price_forecast(ticker: str, as_of: Optional[str] = None) -> dict:
    model, _, X_latest, _, last_close = get_model_artifacts(ticker, as_of=as_of)
    predicted_close = float(model.predict(X_latest)[0])
    change = predicted_close - last_close
    change_pct = (change / last_close) * 100.0 if last_close != 0 else 0.0
    
    # Residual uncertainty approximation (~2% standard error estimate)
    margin = last_close * 0.015
    return {
        "ticker": ticker.strip().upper(),
        "last_close": round(last_close, 2),
        "predicted_close": round(predicted_close, 2),
        "predicted_change": round(change, 2),
        "predicted_change_pct": round(change_pct, 2),
        "direction": "up" if change >= 0 else "down",
        "confidence_low": round(max(0.01, predicted_close - margin), 2),
        "confidence_high": round(predicted_close + margin, 2),
    }


def backtest_model(ticker: str, test_ratio: float = 0.2) -> dict:
    """
    Simulate historical performance of XGBoost on out-of-sample data.
    Computes MAE, RMSE, Directional Accuracy, and Strategy vs Buy & Hold returns.
    """
    if not ticker:
        raise ValueError("Ticker is required for backtesting.")

    ticker = ticker.strip().upper()
    conn = database.get_duckdb_connection()
    try:
        prices = database.fetch_prices_df(conn, ticker, limit=2500)
    finally:
        conn.close()

    if len(prices) < 120:
        raise ValueError("Need at least 120 trading days of history to backtest.")

    feats = make_features(prices, ticker)
    clean_feats = feats.dropna().sort_values("ts").copy()
    if len(clean_feats) < 80:
        raise ValueError("Not enough clean feature rows for backtesting.")

    feature_cols = list(FEATURE_COLS)
    n_total = len(clean_feats)
    n_test = max(20, int(n_total * test_ratio))
    n_train = n_total - n_test

    train_df = clean_feats.iloc[:n_train]
    test_df = clean_feats.iloc[n_train:].copy()

    X_train = train_df[feature_cols]
    y_train = train_df["y"]
    X_test = test_df[feature_cols]
    y_test = test_df["y"]

    model = XGBRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        objective="reg:squarederror",
        random_state=42,
        n_jobs=0,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    # Performance metrics
    diff = y_test.to_numpy() - y_pred
    mae = float(abs(diff).mean())
    rmse = float((diff ** 2).mean() ** 0.5)
    mean_price = float(y_test.mean())
    mape = float((abs(diff) / y_test.to_numpy()).mean()) * 100.0

    # Directional accuracy
    prev_close = test_df["close"].to_numpy()
    actual_dir = np.sign(y_test.to_numpy() - prev_close)
    pred_dir = np.sign(y_pred - prev_close)
    directional_accuracy = float((actual_dir == pred_dir).mean()) * 100.0

    # Strategy Backtest vs Buy & Hold
    actual_returns = (y_test.to_numpy() - prev_close) / prev_close
    # Go long if model predicts positive return, cash (0) otherwise
    strategy_returns = np.where(pred_dir > 0, actual_returns, 0.0)

    cum_bh = np.cumprod(1.0 + actual_returns)
    cum_strat = np.cumprod(1.0 + strategy_returns)

    bh_total_return = float((cum_bh[-1] - 1.0) * 100.0) if len(cum_bh) > 0 else 0.0
    strat_total_return = float((cum_strat[-1] - 1.0) * 100.0) if len(cum_strat) > 0 else 0.0

    dates = [pd.Timestamp(t).strftime("%Y-%m-%d") for t in test_df["ts"]]
    
    chart_points = []
    for i in range(len(dates)):
        chart_points.append({
            "date": dates[i],
            "actual": round(float(y_test.iloc[i]), 2),
            "predicted": round(float(y_pred[i]), 2),
            "buy_and_hold_return": round(float((cum_bh[i] - 1.0) * 100.0), 2),
            "strategy_return": round(float((cum_strat[i] - 1.0) * 100.0), 2),
        })

    return {
        "ticker": ticker,
        "sample_size": n_test,
        "train_size": n_train,
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(mape, 2),
        "directional_accuracy": round(directional_accuracy, 1),
        "buy_and_hold_return": round(bh_total_return, 2),
        "strategy_return": round(strat_total_return, 2),
        "outperformance": round(strat_total_return - bh_total_return, 2),
        "chart_points": chart_points,
    }


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
