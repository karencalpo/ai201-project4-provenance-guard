"""
Integration test for both signals combined

Tests the full pipeline: Signal 1 (Groq) + Signal 2 (Text Stats) → Confidence Score

Requires GROQ_API_KEY to be set in .env file in project root.

Run from project root with:
    python3 tests/test_integration.py

Or run directly from tests folder with:
    python3 test_integration.py
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")

# Add parent directory to path so we can import detection modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from detection.groq_analyzer import analyze_semantic
from detection.scorer import score_confidence
from detection.text_stats import calculate_text_statistics


def test_integration():
    print("=" * 60)
    print("INTEGRATION TEST: Both Signals Combined")
    print("=" * 60)

    if not os.getenv("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY not set")
        print("\nAdd it to .env file in project root:")
        print('  GROQ_API_KEY=your-key-here')
        return False

    # Test cases with different text types
    test_cases = [
        {
            "name": "Natural human narrative",
            "text": "The sun dipped below the horizon, painting the sky in hues of amber and rose. I sat on the porch, coffee in hand, watching the neighborhood slowly go quiet. A dog barked in the distance, then nothing.",
            "expected_classification": "human"
        },
        {
            "name": "Formulaic AI-like text",
            "text": "The implementation of advanced algorithmic systems demonstrates significant potential in enhancing operational efficiency through systematic optimization methodologies.",
            "expected_classification": "uncertain"
        },
        {
            "name": "Mixed/uncertain text",
            "text": "I think the weather is nice today. The weather seems nice. Nice weather makes people happy. I am happy with the weather.",
            "expected_classification": "uncertain"
        },
    ]

    print("\nNote: First test may take 5-10 seconds...\n")

    passed_count = 0
    failed_tests = []

    for i, test_case in enumerate(test_cases, 1):
        print("=" * 60)
        print(f"TEST {i}: {test_case['name']}")
        print("=" * 60)

        text = test_case['text']
        print(f"\nText: {text[:80]}...\n")

        print("Calculating signals...")
        print("-" * 60)

        try:
            # Signal 1: Groq semantic
            print("Signal 1 (Groq Semantic): ", end="", flush=True)
            signal_1 = analyze_semantic(text)
            print(f"{signal_1:.2f}")

            # Signal 2: Text statistics
            print("Signal 2 (Text Stats):    ", end="", flush=True)
            signal_2 = calculate_text_statistics(text)
            print(f"{signal_2:.2f}")

            # Final confidence
            print("-" * 60)
            confidence = score_confidence(signal_1, signal_2)
            print(f"Final Confidence: {confidence:.2f}")

            # Determine classification
            if confidence < 0.20:
                classification = "ai"
                emoji = "🤖"
            elif confidence > 0.80:
                classification = "human"
                emoji = "👤"
            else:
                classification = "uncertain"
                emoji = "❓"

            print(f"Classification: {emoji} {classification}")

            # Show threshold ranges
            print("\nThreshold Analysis:")
            print(f"  < 0.20 (AI):           {confidence < 0.20}")
            print(f"  0.20-0.80 (Uncertain): {0.20 <= confidence <= 0.80}")
            print(f"  > 0.80 (Human):        {confidence > 0.80}")

            # Check if classification matches expected
            expected = test_case['expected_classification']
            matches = classification == expected
            status = "✓ PASS" if matches else "⚠ CHECK"
            print(f"\n{status}: Expected {expected}, got {classification}")

            if matches:
                passed_count += 1
            else:
                failed_tests.append((test_case['name'], expected, classification, confidence))

        except Exception as e:
            print(f"\n✗ ERROR: {e}")
            failed_tests.append((test_case['name'], test_case['expected_classification'], "ERROR", str(e)))

        print()

    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    total_tests = len(test_cases)

    print(f"\nIntegration Tests: {passed_count}/{total_tests} passed")

    if failed_tests:
        print(f"\n⚠ Tests with Unexpected Classification ({len(failed_tests)}):")
        for name, expected, got, confidence in failed_tests:
            if isinstance(confidence, (int, float)):
                print(f"  - {name}: expected {expected}, got {got} (confidence: {confidence:.2f})")
            else:
                print(f"  - {name}: expected {expected}, got {got} (error: {confidence})")

    print("\n" + "=" * 60)
    if passed_count == total_tests:
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return True
    else:
        print(f"⚠ {total_tests - passed_count} TESTS WITH UNEXPECTED CLASSIFICATION")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = test_integration()
    exit(0 if success else 1)
