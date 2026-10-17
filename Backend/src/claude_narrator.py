import os
from pathlib import Path
from typing import Dict, List, Tuple
import httpx
from dotenv import load_dotenv

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def _load_env() -> None:
    curr = Path(__file__).resolve().parent
    for p in [curr.parent.parent, curr.parent, Path.cwd()]:
        env_f = p / ".env"
        if env_f.exists():
            load_dotenv(env_f)
            break


def _friendly_feature_name(name: str) -> str:
    mapping = {
        "ret_1": "1-Day Return momentum",
        "ret_5": "5-Day Return momentum",
        "vol_5": "short-term volatility (5-day)",
        "vol_20": "medium-term volatility (20-day)",
        "ma_5": "5-day moving average",
        "ma_20": "20-day moving average",
        "ma_50": "50-day moving average",
        "ma_ratio": "moving average convergence ratio",
        "price_vs_ma50": "price position relative to 50-day average",
        "range": "daily intraday trading range",
        "vol_chg": "volume flow expansion",
        "vol_regime": "volatility regime indicator",
        "vix_close": "macro VIX market risk level",
        "vix_change": "macro VIX change",
        "sentiment_score": "news sentiment catalyst score",
    }
    return mapping.get(name, name.replace("_", " "))


def _generate_quant_narrative(
    ticker: str,
    regime: str,
    predicted_next_close: float,
    last_close: float,
    explanation: Dict[str, float],
) -> str:
    """Generate high-quality 3-sentence quantitative equity research narrative."""
    change = predicted_next_close - last_close
    change_pct = (change / last_close) * 100.0 if last_close != 0 else 0.0
    dir_str = "upside expansion" if change >= 0 else "downside retracement"
    sign_str = "+" if change >= 0 else ""
    
    # 1. Signal sentence
    s1 = (
        f"FinVizaard's XGBoost predictive model signals potential {dir_str} for {ticker}, "
        f"targeting a next-session close of ${predicted_next_close:.2f} ({sign_str}{change_pct:.2f}% vs "
        f"the latest close of ${last_close:.2f})."
    )

    # 2. Driver & Regime sentence
    sorted_feats = sorted(explanation.items(), key=lambda kv: abs(kv[1]), reverse=True)
    pos_feats = [k for k, v in sorted_feats if v > 0]
    neg_feats = [k for k, v in sorted_feats if v < 0]

    top_pos_desc = _friendly_feature_name(pos_feats[0]) if pos_feats else None
    top_neg_desc = _friendly_feature_name(neg_feats[0]) if neg_feats else None

    regime_desc = {
        "bull": "predominantly bullish market regime",
        "sideways": "range-bound, sideways market regime",
        "bear": "defensive, bearish market regime",
    }.get(regime.lower(), f"{regime} market regime")

    if top_pos_desc and top_neg_desc:
        s2 = (
            f"Under the currently detected {regime_desc}, this projection is primarily supported by {top_pos_desc} "
            f"(+{explanation[pos_feats[0]]:.2f}), while partially moderated by {top_neg_desc} ({explanation[neg_feats[0]]:.2f})."
        )
    elif top_pos_desc:
        s2 = (
            f"Operating within a {regime_desc}, the forecast is strongly bolstered by {top_pos_desc} "
            f"(+{explanation[pos_feats[0]]:.2f}) and positive technical alignment."
        )
    elif top_neg_desc:
        s2 = (
            f"Operating within a {regime_desc}, the forecast faces downward pressure primarily from {top_neg_desc} "
            f"({explanation[neg_feats[0]]:.2f})."
        )
    else:
        s2 = f"The price outlook reflects steady baseline expectations within the current {regime_desc}."

    # 3. Risk / Watch sentence
    if "vol_regime" in explanation or "vix_change" in explanation:
        s3 = "Traders should closely monitor macroeconomic volatility prints and key support levels to validate continuation."
    elif change >= 0:
        s3 = f"Watch for sustained volume confirmation above the ${predicted_next_close:.2f} target level to confirm continuation."
    else:
        s3 = f"Watch for defensive stabilization near ${predicted_next_close:.2f} before considering directional re-entry."

    return f"{s1} {s2} {s3}"


def narrate_explanation(
    ticker: str,
    regime: str,
    predicted_next_close: float,
    last_close: float,
    explanation: Dict[str, float],
) -> str:
    """
    Call Anthropic Messages API or OpenAI Chat Completions API with a structured quant prompt,
    or fall back to a high quality quantitative synthesis.
    """
    if not explanation:
        raise ValueError("Explanation is required.")

    _load_env()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    # Handle if OpenAI key is accidentally placed in ANTHROPIC_API_KEY
    if anthropic_key.startswith("sk-proj-") and not openai_key:
        openai_key = anthropic_key
        anthropic_key = ""

    top5: List[Tuple[str, float]] = sorted(
        explanation.items(), key=lambda kv: abs(kv[1]), reverse=True
    )[:5]
    top_lines = "\n".join(f"  - {_friendly_feature_name(name)}: {value:+.4f}" for name, value in top5)

    user_prompt = f"""You are a senior equity quantitative analyst. Write a concise 3-sentence note for institutional investors.

Ticker: {ticker}
Current HMM Regime: {regime}
Latest Close: ${last_close:.2f}
Predicted Next Close: ${predicted_next_close:.2f}
Top SHAP feature contributions (dollars vs prior close):
{top_lines}

Respond in EXACTLY 3 sentences:
1) Signal: The directional prediction for {ticker} including target price and % difference.
2) Rationale: Tie the prediction to the HMM regime and the top SHAP drivers.
3) Risk/Monitor: Key price level, volatility catalyst, or metric to watch next.

Do not use bullet points or markdown headings. Write exactly 3 sentences."""

    # 1. Try Anthropic
    if anthropic_key and anthropic_key.startswith("sk-ant-"):
        try:
            payload = {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": user_prompt}],
            }
            headers = {
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(_ANTHROPIC_URL, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    blocks = data.get("content") or []
                    texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
                    text = "".join(texts).strip()
                    if text:
                        return text
        except Exception:
            pass

    # 2. Try OpenAI
    if openai_key and (openai_key.startswith("sk-") or openai_key.startswith("sk-proj-")):
        try:
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": user_prompt}],
                "max_tokens": 300,
            }
            headers = {
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            }
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(_OPENAI_URL, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["choices"][0]["message"]["content"].strip()
                    if text:
                        return text
        except Exception:
            pass

    # 3. High quality local quant synthesis
    return _generate_quant_narrative(
        ticker=ticker,
        regime=regime,
        predicted_next_close=predicted_next_close,
        last_close=last_close,
        explanation=explanation,
    )

