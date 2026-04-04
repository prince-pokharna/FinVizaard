from typing import Dict, List, Optional, TypedDict

import numpy as np
import shap

from . import xgboost_model


class ExplainResult(TypedDict):
    explanation: Dict[str, float]
    base_value: float
    predicted_value: float
    last_close: float
    feature_columns: List[str]


def explain_prediction(ticker: str, as_of: Optional[str] = None) -> ExplainResult:
    if not ticker:
        raise ValueError("Ticker is required.")

    model, feature_cols, X_latest, X_bg, last_close = xgboost_model.get_model_artifacts(
        ticker, as_of=as_of
    )
    explainer = shap.TreeExplainer(model, data=X_bg, feature_names=feature_cols)
    shap_values = explainer.shap_values(X_latest)

    # shap returns shape (n_features,) for single row
    vals = shap_values[0] if hasattr(shap_values, "__len__") else shap_values
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
    }
