"""
Confidence Scorer: Weighted Ensemble Combiner

Combines two complementary signals via weighted ensemble to produce a final confidence score.

Signals Combined:
  - Signal 1 (Groq Semantic Analysis): 70% weight
  - Signal 2 (Stylometric Analysis): 30% weight

Output: Single score 0.0-1.0 with interpretation:
  - 0.0 - 0.20: High-confidence AI-generated
  - 0.20 - 0.80: Uncertain (requires manual review)
  - 0.80 - 1.0: High-confidence human-written
"""


def score_confidence(signal_1_score: float, signal_2_score: float) -> float:
    """
    Combine two signals via weighted ensemble.

    Applies weighted averaging formula:
        final_confidence = (0.70 × signal_1_score) + (0.30 × signal_2_score)

    The 70/30 weighting prioritizes semantic analysis (Groq) over stylometrics
    since semantic understanding is a stronger indicator of human authorship.

    Args:
        signal_1_score (float): Groq semantic analysis score (0.0-1.0)
        signal_2_score (float): Stylometric analysis score (0.0-1.0)

    Returns:
        float: Final confidence score (0.0-1.0)
               0.0 = high-confidence AI-generated
               0.5 = uncertain
               1.0 = high-confidence human-written

    Examples:
        >>> score_confidence(0.0, 0.0)
        0.0
        >>> score_confidence(1.0, 1.0)
        1.0
        >>> score_confidence(0.5, 0.5)
        0.5
        >>> score_confidence(0.8, 0.2)
        0.68
        >>> score_confidence(0.2, 0.8)
        0.38
    """
    # Validate input ranges
    signal_1_score = max(0.0, min(1.0, signal_1_score))
    signal_2_score = max(0.0, min(1.0, signal_2_score))

    # Apply weighted ensemble formula
    # Signal 1 (Groq semantic): 70% | Signal 2 (Stylometric): 30%
    final_confidence = (0.70 * signal_1_score) + (0.30 * signal_2_score)

    # Clamp output to valid range [0.0, 1.0]
    final_confidence = max(0.0, min(1.0, final_confidence))

    return final_confidence
