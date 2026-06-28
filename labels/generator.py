"""
Label Generator: Map confidence scores to transparency labels.

Converts confidence scores (0.0-1.0) into plain-language transparency text
that non-technical readers can understand.

Three distinct label variants based on thresholds:
  - High-Confidence AI (< 0.20): "This appears to be AI-generated content"
  - Uncertain (0.20-0.80): "We're uncertain about the origin..."
  - High-Confidence Human (> 0.80): "This appears to be written by a human"
"""


def generate_label(confidence: float) -> dict:
    """
    Map confidence score to transparency label and classification.

    Args:
        confidence (float): Score 0.0-1.0 from confidence scorer
                           (0.0 = definitely AI, 1.0 = definitely human)

    Returns:
        dict: {
            "classification": "ai" | "uncertain" | "human",
            "label": "Plain language transparency text...",
            "confidence": confidence (echoed back for reference)
        }

    Thresholds:
      - < 0.20: High-confidence AI
      - 0.20-0.80: Uncertain (both signals disagree or are weak)
      - > 0.80: High-confidence human

    Design Notes:
    - Classification uses string identifiers (not "likely_ai" or "possibly_human")
      for clarity and API consistency
    - Labels use "appears to be" rather than definitive statements
      to acknowledge that no detection system is 100% accurate
    - Uncertain label explicitly acknowledges both possibilities
      rather than hedging with weak language
    """
    # Clamp confidence to valid range
    confidence = max(0.0, min(1.0, confidence))

    if confidence < 0.35:
        return {
            "classification": "ai",
            "label": "This appears to be AI-generated content",
            "confidence": round(confidence, 2)
        }
    elif confidence > 0.70:
        return {
            "classification": "human",
            "label": "This appears to be written by a human",
            "confidence": round(confidence, 2)
        }
    else:
        return {
            "classification": "uncertain",
            "label": "We're uncertain about the origin of this content. It may be AI-generated or human-written.",
            "confidence": round(confidence, 2)
        }


def get_classification(confidence: float) -> str:
    """
    Get just the classification string for a confidence score.

    Args:
        confidence (float): Score 0.0-1.0

    Returns:
        str: "ai" | "uncertain" | "human"
    """
    result = generate_label(confidence)
    return result["classification"]


def get_label_text(confidence: float) -> str:
    """
    Get just the label text for a confidence score.

    Args:
        confidence (float): Score 0.0-1.0

    Returns:
        str: Plain language transparency label
    """
    result = generate_label(confidence)
    return result["label"]
