from typing import Dict, Optional

import shap

from . import xgboost_model


def explain_prediction(ticker: str, as_of: Optional[str] = None) -> Dict[str, float]:
    if not ticker:
        raise ValueError("Ticker is required.")

    model, feature_cols, X_latest, X_bg = xgboost_model.get_model_artifacts(ticker, as_of=as_of)
    explainer = shap.TreeExplainer(model, data=X_bg, feature_names=feature_cols)
    shap_values = explainer.shap_values(X_latest)

    # shap returns shape (n_features,) for single row
    vals = shap_values[0] if hasattr(shap_values, "__len__") else shap_values
    out = {feature_cols[i]: float(vals[i]) for i in range(len(feature_cols))}
    return out

