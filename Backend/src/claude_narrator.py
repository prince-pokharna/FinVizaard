from typing import Dict


def narrate_explanation(explanation: Dict[str, float]) -> str:
    """
    Placeholder text generation for explanations.
    Later this can call Claude/OpenAI via httpx with your API key.
    """
    if not explanation:
        raise ValueError("Explanation is required.")

    parts = []
    for feature, value in explanation.items():
        weight = round(value * 100)
        parts.append(f"{feature.replace('_', ' ')} contributes about {weight}% to the prediction")

    return " ; ".join(parts)

