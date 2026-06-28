"""
Signal 1: Semantic Analyzer via Groq API

Detects AI-generation patterns by identifying corporate/academic jargon, lack of authentic details, and formulaic reasoning.

Weight: 70% of final confidence score

Measurements:
  - Corporate/academic jargon: Detects vague phrases like "demonstrates potential", "enhances efficiency", "systematic optimization"
  - Abstract noun chains: Flags "systems", "methodologies", "frameworks" without concrete examples
  - Specific details & anecdotes: Scores higher when text includes personal examples, concrete anecdotes, genuine perspective
  - Authentic voice: Detects informal language, conversational tone, human quirks vs. "perfect" grammar
  - Genuine reasoning: Looks for unexpected connections and novel insights vs. formulaic reasoning chains

Output: Single score 0.0-1.0 (higher = more likely human-written)

Why This Signal:
  - Catches AI patterns that pure statistics miss
  - Leverages language model understanding of authenticity
  - Fast enough for real-time classification (single API call)

Blind Spots:
  - Can't detect AI trained to mimic authenticity (anecdotes, conversational tone)
  - Humans writing formally without jargon may score as AI
  - Expert technical writing naturally uses abstract nouns; may be misclassified
  - Casual writing without anecdotes might score low (AI-like) despite being human
  - Non-English or translated content (Groq training is English-heavy)
  - Very specific domains with domain-specific language

Test Cases:
  - AI-generated: Formulaic jargon, pattern matching → ~0.1-0.3
  - Human-written: Natural flow, anecdotes, authentic voice → ~0.7-0.9
  - Mixed/uncertain: → ~0.4-0.6
"""

import os
from groq import Groq, RateLimitError, APITimeoutError, APIConnectionError


def analyze_semantic(text: str) -> float:
    """
    Analyze text semantics using Groq API.

    Sends text to Groq's llama-3.3-70b-versatile model with a structured prompt
    asking for probability of human authorship (0.0-1.0).

    Args:
        text (str): Text to analyze (10-10,000 characters)

    Returns:
        float: Score 0.0-1.0 (higher = more likely human-written)
               Returns 0.5 on API failure or invalid input

    Implementation notes:
    - Uses Groq API (free tier: 30 calls/minute, 300/day)
    - Model: llama-3.3-70b-versatile
    - Requires GROQ_API_KEY environment variable
    - Includes automatic retries on rate limits
    - Falls back to neutral 0.5 on any error
    """
    # Input validation
    if not text or len(text) < 10:
        return 0.5

    text = text.strip()
    if len(text) < 10:
        return 0.5

    # Retrieve API key from environment
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Warning: GROQ_API_KEY not set. Returning neutral score.")
        return 0.5

    # Initialize Groq client
    client = Groq(api_key=api_key)

    # Construct prompt following the specification
    prompt = f"""Rate this text for likelihood of being AI-generated. Look for SPECIFIC patterns, not impressions.

SCORE LOW (AI-likely) IF YOU FIND:
1. Heavy use of placeholder language: "various sectors", "stakeholders", "considerations"
2. False balance structure: Presents both sides of simple topic without actual disagreement
3. Vague corporate phrases that repeat across AI texts: "paradigm shift", "transformative", "essential to consider"
4. Lists formatted as "on one hand... on the other hand" with NO personal judgment
5. Passive voice overuse - hides who is doing what
6. Missing concrete details (no specific names, dates, examples, numbers)
7. Generic closing that doesn't commit to anything

SCORE HIGH (Human-likely) IF YOU FIND:
1. Specific claims with checkable details (names, dates, places, numbers)
2. Personal voice: "I think", "I noticed", "in my experience"
3. Unexpected statement or disagreement (not both-sides platitudes)
4. Personal emotion or reaction (even if restrained)
5. Mistakes, errors, or self-correction that shows thinking
6. Specificity that could only come from direct experience
7. Taking a clear position despite acknowledging complexity

Text:
{text}

Count the patterns:
- How many AI-likely patterns do you see? (count: 0-7)
- How many human-likely patterns do you see? (count: 0-7)

Respond with a single decimal between 0.0-1.0:
- 0.0 = clear AI (6+ AI patterns, 0-1 human patterns)
- 0.3 = probable AI (4-5 AI patterns, 0-2 human patterns)
- 0.5 = unclear (2-3 patterns each, or no clear patterns)
- 0.7 = probable human (0-2 AI patterns, 4-5 human patterns)
- 1.0 = clear human (0-1 AI patterns, 6+ human patterns)

Output ONLY the number, nothing else."""

    # Make API call with retry logic for rate limits
    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0,
                max_tokens=10
            )

            # Extract content from response
            content = response.choices[0].message.content.strip()

            # Parse the score from response
            try:
                score = float(content)
                if 0.0 <= score <= 1.0:
                    return score
                else:
                    print(f"Warning: Score {score} outside [0.0, 1.0]. Returning neutral score.")
                    return 0.5
            except ValueError:
                print(f"Warning: Could not parse score from response: '{content}'. Returning neutral score.")
                return 0.5

        except RateLimitError:
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            else:
                print("Warning: Rate limit exceeded after retries. Returning neutral score.")
                return 0.5
        except APITimeoutError:
            print("Warning: Groq API timeout. Returning neutral score.")
            return 0.5
        except APIConnectionError as e:
            print(f"Warning: Groq API connection failed: {e}. Returning neutral score.")
            return 0.5
        except Exception as e:
            print(f"Warning: Unexpected error during Groq API call: {e}. Returning neutral score.")
            return 0.5

    return 0.5
