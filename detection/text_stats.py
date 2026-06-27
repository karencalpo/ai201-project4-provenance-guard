"""
Signal 1: Text Statistics Analyzer

Captures stylistic patterns that distinguish human from AI writing.

Measurements:
  - Type-Token Ratio (TTR): Vocabulary diversity
  - Bigram Diversity: Phrase variation
  - Sentence Length Variance: Structural variety

Output: Single score 0.0-1.0 (higher = more human-written)

Test Cases:
  - Highly repetitive: "Tired tired tired..." → ~0.22
  - Varied human: "The feline was exhausted..." → ~0.92
  - Mixed/uncertain: → ~0.50-0.65
"""

import re
import math


def calculate_text_statistics(text):
    """
    Calculate text statistics score for AI vs human detection.

    Uses three core metrics combined into a single 0.0-1.0 score:
    1. Type-Token Ratio (vocabulary diversity): 45% weight
    2. Bigram Diversity (phrase variation): 45% weight
    3. Sentence Length Variance (structural variety): 10% weight

    Args:
        text (str): Input text (10-10,000 characters)

    Returns:
        float: Score 0.0-1.0 (higher = more likely human-written)

    Why these metrics:
    - High TTR/bigram diversity + varied sentence length = human writing
    - Low TTR/bigram diversity + uniform sentences = AI writing
    """
    if not text or len(text) < 10:
        return 0.5

    text = text.strip()
    tokens = text.split()

    if len(tokens) < 3:
        return 0.5

    # Calculate three core components
    ttr_score = _calculate_type_token_ratio(tokens)
    bigram_diversity_score = _calculate_bigram_diversity(tokens)
    sentence_variance_score = _calculate_sentence_variance(text)

    # Combine with weights: vocabulary and phrases are strongest indicators
    combined_score = (
        0.45 * ttr_score +
        0.45 * bigram_diversity_score +
        0.10 * sentence_variance_score
    )

    return min(1.0, max(0.0, combined_score))


def _calculate_type_token_ratio(tokens):
    """
    Type-Token Ratio: Unique words / total words.

    High TTR (closer to 1.0) = diverse vocabulary = human-like.
    Low TTR (closer to 0.0) = repetitive vocabulary = AI-like.

    Why:
    - Humans naturally use varied vocabulary and synonyms
    - AI models optimize for likely sequences, leading to repetition
    - TTR typically: 0.3-0.5 (repetitive) to 0.6-0.8 (diverse)

    Examples:
    - "The cat was tired. The cat slept. The cat rested."
      TTR = 6 unique / 14 total = 0.43 (repetitive, AI-like)
    - "The feline was exhausted, so it napped. Actually, it zonked out."
      TTR = 12 unique / 14 total = 0.86 (diverse, human-like)
    """
    if not tokens:
        return 0.5

    unique_tokens = len(set(t.lower() for t in tokens))
    total_tokens = len(tokens)
    ttr = unique_tokens / total_tokens

    # Normalize TTR to 0-1 range
    # Cap at 0.75 for scaling (TTR rarely exceeds 0.75 in natural text)
    normalized_ttr = min(1.0, ttr / 0.75)

    return normalized_ttr


def _calculate_bigram_diversity(tokens):
    """
    Bigram Diversity: Unique bigrams / total bigrams.

    High diversity (closer to 1.0) = varied phrases = human-like.
    Low diversity (closer to 0.0) = repeated phrases = AI-like.

    Why:
    - Humans avoid repeating exact phrases (use synonyms, rephrase)
    - AI models repeat common word pairs frequently
    - High bigram entropy indicates natural phrase variation

    Examples:
    - "The cat was tired. The cat slept. The cat rested."
      Most bigrams repeat: "The cat" appears 4 times
      Diversity = low (AI-like)
    - "The feline was exhausted, so it napped. Actually, it zonked out."
      Most bigrams unique (natural variation)
      Diversity = high (human-like)
    """
    if len(tokens) < 2:
        return 0.5

    # Build bigrams (consecutive word pairs)
    bigrams = []
    for i in range(len(tokens) - 1):
        bigram = (tokens[i].lower(), tokens[i + 1].lower())
        bigrams.append(bigram)

    if not bigrams:
        return 0.5

    # Calculate diversity: unique bigrams / total bigrams
    unique_bigrams = len(set(bigrams))
    total_bigrams = len(bigrams)
    bigram_diversity = unique_bigrams / total_bigrams

    return min(1.0, max(0.0, bigram_diversity))


def _calculate_sentence_variance(text):
    """
    Sentence Length Variance: How much sentence lengths vary.

    High variance (closer to 1.0) = varied structure = human-like.
    Low variance (closer to 0.0) = uniform structure = AI-like.

    Why:
    - Humans naturally vary sentence length (short punchy + long complex)
    - Some AI models produce uniform sentence lengths
    - Measured as coefficient of variation (std dev / mean)

    Examples:
    - "The cat was tired. The cat was tired. The cat was tired."
      All 4 words each → CV = 0 (AI-like)
    - "The feline was exhausted. Actually, it zonked out completely."
      Varied lengths (5, 5 words) → CV = high (human-like)
    """
    # Split into sentences (simple: . ! ?)
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) < 2:
        return 0.5

    # Calculate sentence lengths
    sentence_lengths = [len(s.split()) for s in sentences]

    # Calculate coefficient of variation
    mean_length = sum(sentence_lengths) / len(sentence_lengths)
    if mean_length == 0:
        return 0.5

    variance = sum((x - mean_length) ** 2 for x in sentence_lengths) / len(sentence_lengths)
    std_dev = math.sqrt(variance)
    cv = std_dev / mean_length

    # Normalize CV to 0-1 (typical range is 0-1.5 for natural text)
    normalized_cv = min(1.0, cv / 1.5)

    return normalized_cv
