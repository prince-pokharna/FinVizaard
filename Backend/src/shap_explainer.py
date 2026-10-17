from typing import Dict, List, Optional, TypedDict

import numpy as np
import shap

from . import xgboost_model


FEATURE_METADATA = {
    "ret_1": {"label": "1-Day Return", "desc": "Percentage price change over the prior trading day"},
    "ret_5": {"label": "5-Day Return", "desc": "Cumulative price return over 5 trading days"},
    "vol_5": {"label": "5-Day Volatility", "desc": "Standard deviation of daily returns over 5 days"},
    "vol_20": {"label": "20-Day Volatility", "desc": "Standard deviation of daily returns over 20 days"},
    "ma_5": {"label": "5-Day Moving Avg", "desc": "5-day simple moving average price"},
    "ma_20": {"label": "20-Day Moving Avg", "desc": "20-day simple moving average price"},
    "ma_50": {"label": "50-Day Moving Avg", "desc": "50-day simple moving average price"},
    "ma_ratio": {"label": "MA Ratio (5/20)", "desc": "Ratio of 5-day MA to 20-day MA (short vs medium trend)"},
    "price_vs_ma50": {"label": "Price vs 50MA", "desc": "Current close divided by 50-day MA"},
    "range": {"label": "Intraday Range", "desc": "Intraday spread (High - Low) divided by Close"},
    "vol_chg": {"label": "Volume Change", "desc": "Day-over-day percentage change in trading volume"},
    "vol_regime": {"label": "Vol Regime Alert", "desc": "Flag indicating volatility spike above 1.5x historical norm"},
    "vix_close": {"label": "CBOE VIX Index", "desc": "Market-wide volatility and risk index level"},
    "vix_change": {"label": "VIX Daily Change", "desc": "Daily percentage change in market volatility index"},
    "sentiment_score": {"label": "News Sentiment", "desc": "AI/NLP sentiment score (-1 to +1) from live news headlines"},
}


class ExplainResult(TypedDict):
    explanation: Dict[str, float]
    base_value: float
    predicted_value: float
    last_close: float
    feature_columns: List[str]
    feature_metadata: Dict[str, dict]


def explain_prediction(ticker: str, as_of: Optional[str] = None) -> ExplainResult:
    if not ticker:
        raise ValueError("Ticker is required.")

    model, feature_cols, X_latest, X_bg, last_close = xgboost_model.get_model_artifacts(
        ticker, as_of=as_of
    )
    explainer = shap.TreeExplainer(model, data=X_bg, feature_names=feature_cols)
    shap_values = explainer.shap_values(X_latest)

    # shap returns shape (1, n_features) or (n_features,)
    if hasattr(shap_values, "ndim") and shap_values.ndim > 1:
        vals = shap_values[0]
    elif hasattr(shap_values, "__len__") and len(shap_values) > 0 and hasattr(shap_values[0], "__len__"):
        vals = shap_values[0]
    else:
        vals = shap_values

    out = {feature_cols[i]: float(vals[i]) for i in range(len(feature_cols))}

    ev = explainer.expected_value
    base_value = float(np.asarray(ev, dtype=float).ravel()[0])
    predicted_value = float(model.predict(X_latest)[0])

    return {
        "explanation": out,
        "base_value": base_value,
        "predicted_value": predicted_value,
        "last_close": last_close,
        "feature_columns": list(feature_cols),
        "feature_metadata": FEATURE_METADATA,
    }

