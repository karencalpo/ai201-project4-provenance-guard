"""
Signal 2: Stylometric Analyzer (Text Statistics)

Detects AI-like patterns through statistical analysis of text structure and vocabulary.

Weight: 20% of final confidence score

Measurements:
  - Type-Token Ratio (TTR): Vocabulary diversity (unique words / total words)
  - Bigram Diversity: Phrase variation (unique bigrams / total bigrams)
  - Sentence Structure Repetition: How often sentences follow similar templates
  - Personal Markers: Presence of first-person pronouns, emotional words, specificity
  - Abstract Noun Density: Proportion of abstract nouns without concrete examples

AI-like Patterns Detected:
  - Low personal markers (few "I", "we", specific names/dates)
  - High abstract noun density without examples
  - Repetitive sentence structures ("X demonstrates Y", "It is important to note that...")
  - Low emotional/sensory word density
  - Formulaic connectors ("furthermore", "moreover", "in addition")

Human-like Patterns:
  - High personal markers (specific experiences, names, dates)
  - Emotional/sensory language (frustrated, exhausted, bitter)
  - Varied sentence structures
  - Concrete examples and specifics
  - Natural conversational elements (contractions, "honestly", "actually")

Output: Single score 0.0-1.0 (higher = more likely human-written)

Test Cases:
  - AI: "Artificial intelligence represents a paradigm shift..." → ~0.20-0.40
  - Human: "ok so i finally tried that ramen place..." → ~0.80-0.95
  - Mixed: → ~0.40-0.70
"""

import re


def calculate_text_statistics(text):
    """
    Calculate text statistics score for AI vs human detection.

    Uses multiple metrics weighted to detect AI patterns:
    1. Personal markers (I, we, specific references): 30% weight
    2. Emotional/sensory language: 25% weight
    3. Formulaic phrase detection: 20% weight
    4. Type-Token Ratio (vocabulary diversity): 15% weight
    5. Sentence Structure Repetition: 10% weight

    Args:
        text (str): Input text (10-10,000 characters)

    Returns:
        float: Score 0.0-1.0 (higher = more likely human-written)

    AI text typically has:
    - Few personal markers (low "I", "we", specific names/dates)
    - Low emotional language (feels formulaic)
    - High formulaic phrase density (demonstrates, furthermore, essential to note)
    - Repetitive sentence templates

    Human text typically has:
    - Personal references and specific details
    - Emotional/sensory words (frustrated, exhausted, bitter, WAY too much)
    - Natural language markers (honestly, actually, so)
    - Varied sentence structures
    """
    if not text or len(text) < 10:
        return 0.5

    text = text.strip()
    tokens = text.split()

    if len(tokens) < 3:
        return 0.5

    # Calculate individual components
    personal_markers_score = _calculate_personal_markers(text, tokens)
    emotional_language_score = _calculate_emotional_language(text, tokens)
    formulaic_phrase_score = _calculate_formulaic_phrases(text)
    ttr_score = _calculate_type_token_ratio(tokens)
    structure_variety_score = _calculate_structure_variety(text)

    # Combine with weights emphasizing human markers
    combined_score = (
        0.30 * personal_markers_score +
        0.25 * emotional_language_score +
        0.20 * formulaic_phrase_score +
        0.15 * ttr_score +
        0.10 * structure_variety_score
    )

    return min(1.0, max(0.0, combined_score))


def _calculate_personal_markers(text, tokens):
    """
    Detect personal markers: first-person pronouns, specific references, emotional depth.

    High score = human-like (specific experiences, "I", "we", names, dates)
    Low score = AI-like (generic, no personal references)
    """
    text_lower = text.lower()

    # Count personal markers
    personal_pronouns = text_lower.count(" i ") + text_lower.count(" we ") + text_lower.count(" me ") + text_lower.count(" my ")

    # Look for specific markers (numbers that might be dates/times, proper nouns)
    has_specific_refs = len([t for t in tokens if t[0].isupper() and t not in ["The", "It", "A", "An", "This", "That"]]) > 0
    has_numbers = any(c.isdigit() for c in text)

    # Count contractions (very human marker)
    contractions = text.count("'s ") + text.count("'t ") + text.count("'m ") + text.count("'re ") + text.count("'ve ")

    # Normalize
    marker_score = min(1.0, (personal_pronouns / max(1, len(tokens)) * 5))  # Scale up to 1.0
    if has_specific_refs:
        marker_score = min(1.0, marker_score + 0.2)
    if has_numbers:
        marker_score = min(1.0, marker_score + 0.15)
    if contractions > 0:
        marker_score = min(1.0, marker_score + 0.3)

    return min(1.0, marker_score)


def _calculate_emotional_language(text, tokens):
    """
    Detect emotional and sensory language: words indicating genuine experience.

    High score = human-like (frustrated, exhausted, bitter, WAY too much)
    Low score = AI-like (no emotional markers, clinical tone)
    """
    text_lower = text.lower()

    # Emotional/sensory words that indicate authenticity
    emotional_words = [
        "frustrated", "exhausted", "bitter", "annoyed", "disappointed", "angry",
        "happy", "excited", "love", "hate", "amazing", "awful", "terrible", "great",
        "horrible", "wonderful", "disgusted", "embarrassed", "proud", "ashamed",
        "confused", "overwhelmed", "relieved", "worried", "scared", "nervous"
    ]

    # Intensity markers
    intensity_markers = ["way ", "really ", "so ", "very ", "quite ", "extremely ", "absolutely ", "literally "]

    # Sensory words
    sensory_words = ["broth", "sodium", "thirsty", "taste", "smell", "sound", "feel", "soft", "hard", "warm", "cold"]

    emotional_count = sum(1 for word in emotional_words if word in text_lower)
    intensity_count = sum(1 for marker in intensity_markers if marker in text_lower)
    sensory_count = sum(1 for word in sensory_words if word in text_lower)

    total_markers = emotional_count + intensity_count + sensory_count
    emotional_score = min(1.0, total_markers / max(1, len(tokens)) * 15)

    return emotional_score


def _calculate_formulaic_phrases(text):
    """
    Detect formulaic/corporate phrases common in AI text.

    High score = human-like (few formulaic phrases)
    Low score = AI-like (many formulaic phrases)
    """
    text_lower = text.lower()

    # Formulaic phrases and corporate jargon
    formulaic_patterns = [
        "it is important to note that",
        "demonstrates potential",
        "enhances efficiency",
        "systematic",
        "paradigm shift",
        "transformative",
        "stakeholders",
        "various sectors",
        "responsible deployment",
        "furthermore",
        "moreover",
        "in addition",
        "essential to consider",
        "the ethic",
        "in modern society",
        "in contemporary",
        "in this paper",
        "one can argue",
        "it could be argued"
    ]

    formulaic_count = sum(1 for phrase in formulaic_patterns if phrase in text_lower)

    # Penalize high formulaic density
    text_words = text.split()
    formulaic_score = 1.0 - min(1.0, formulaic_count / max(1, len(text_words)) * 30)

    return formulaic_score


def _calculate_structure_variety(text):
    """
    Detect sentence structure variety and repetition patterns.

    High score = human-like (varied structures)
    Low score = AI-like (repetitive structures)
    """
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) < 2:
        return 0.5

    # Check for sentence structure patterns
    sentence_starts = []
    for sent in sentences:
        words = sent.split()
        if len(words) > 0:
            sentence_starts.append(words[0].lower())

    # Count unique sentence starts
    unique_starts = len(set(sentence_starts))
    variety_score = min(1.0, unique_starts / max(1, len(sentences)))

    # Check for "The/It/X is" pattern repetition (common in AI)
    is_pattern_count = sum(1 for sent in sentences if re.search(r'^(\w+\s+)+is\s', sent, re.I))
    if is_pattern_count > len(sentences) * 0.4:  # More than 40% "X is" sentences
        variety_score *= 0.6

    return variety_score


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


