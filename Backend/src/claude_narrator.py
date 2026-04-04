from typing import Dict, List, Tuple

import httpx
from dotenv import load_dotenv
import os
from pathlib import Path

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-opus-4-6"


def _load_env() -> None:
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env")


def _fallback_narrative(explanation: Dict[str, float]) -> str:
    if not explanation:
        return "No SHAP explanation available for a template summary."
    ranked: List[Tuple[str, float]] = sorted(
        explanation.items(), key=lambda kv: abs(kv[1]), reverse=True
    )
    parts = []
    for feature, value in ranked:
        parts.append(
            f"{feature.replace('_', ' ')} impact on predicted next close: {value:+.4f} (model units)"
        )
    return " ; ".join(parts)


def narrate_explanation(
    ticker: str,
    regime: str,
    predicted_next_close: float,
    last_close: float,
    explanation: Dict[str, float],
) -> str:
    """
    Call Anthropic Messages API with a structured quant prompt, or fall back to a
    dollar-impact template if the key is missing or the request fails.
    """
    if not explanation:
        raise ValueError("Explanation is required.")

    _load_env()
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key or api_key == "your_key_here":
        return _fallback_narrative(explanation)

    top5: List[Tuple[str, float]] = sorted(
        explanation.items(), key=lambda kv: abs(kv[1]), reverse=True
    )[:5]
    top_lines = "\n".join(f"  - {name}: {value:+.6f}" for name, value in top5)

    user_prompt = f"""You are a concise equity quant analyst. Use only the facts below.

Ticker: {ticker}
Current regime (HMM label): {regime}
Predicted next close (XGBoost): {predicted_next_close:.6f}
Latest observed close: {last_close:.6f}
Top 5 SHAP feature contributions (same units as the prediction — dollars vs prior close level, not percentages):
{top_lines}

Respond in exactly 3 sentences with this structure:
1) What the model is signaling for this name.
2) Why — tie it to the regime and the strongest SHAP drivers.
3) What to watch next (risks or data to monitor).

Do not use bullet points. Do not claim these SHAP values are percentages."""

    payload = {
        "model": _MODEL,
        "max_tokens": 512,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(_ANTHROPIC_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        blocks = data.get("content") or []
        texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
        text = "".join(texts).strip()
        if not text:
            return _fallback_narrative(explanation)
        return text
    except Exception:
        return _fallback_narrative(explanation)
