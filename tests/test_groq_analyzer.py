"""
Test suite for groq_analyzer.py (Signal 1 semantic analyzer)

Requires GROQ_API_KEY to be set in .env file in project root.

Run from project root with:
    python3 tests/test_groq_analyzer.py

Or run directly from tests folder with:
    python3 test_groq_analyzer.py
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


def test_groq_analyzer():
    print("=" * 60)
    print("GROQ SEMANTIC ANALYZER TESTS")
    print("=" * 60)

    # Check API key is set
    if not os.getenv("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY not set")
        print("\nAdd it to .env file in project root:")
        print('  GROQ_API_KEY=your-key-here')
        return False

    # Test cases
    test_texts = [
        {
            "name": "Human-written (natural narrative)",
            "text": "The sun dipped below the horizon, painting the sky in hues of amber and rose. I sat on the porch, coffee in hand, watching the neighborhood slowly go quiet.",
            "expect_range": (0.65, 1.0),
            "description": "Natural writing with descriptive language"
        },
        {
            "name": "Formulaic text (likely AI)",
            "text": "The utilization of artificial intelligence in contemporary technological ecosystems represents a paradigm shift in computational methodologies. This transformation facilitates enhanced efficiency metrics across multifaceted operational frameworks.",
            "expect_range": (0.0, 0.35),
            "description": "Overly formal, formulaic phrasing"
        },
        {
            "name": "Mixed/uncertain text",
            "text": "I went to the store. The store had apples. I like apples. I bought some apples.",
            "expect_range": (0.5, 1.0),
            "description": "Simple but repetitive (lacks jargon, has concrete details)"
        },
    ]

    print("\nNote: First call may take 5-10 seconds...\n")

    passed_count = 0
    failed_tests = []

    for test in test_texts:
        print(f"\nTest: {test['name']}")
        print(f"Description: {test['description']}")
        print(f"Text: {test['text'][:60]}...")

        try:
            score = analyze_semantic(test['text'])
            low, high = test['expect_range']
            in_range = low <= score <= high
            status = "✓ PASS" if in_range else "⚠ WARNING"

            print(f"{status}: Score {score:.2f}")
            print(f"Expected range: {low}-{high}")

            if in_range:
                passed_count += 1
            else:
                print(f"  Note: Score outside expected range")
                failed_tests.append((test['name'], f"{low}-{high}", score))

        except Exception as e:
            print(f"✗ ERROR: {e}")
            failed_tests.append((test['name'], "No error", str(e)))

    # Edge case tests
    print("\n" + "=" * 60)
    print("EDGE CASES")
    print("=" * 60)

    edge_cases = [
        ("", "Empty text", 0.5),
        ("short", "Too short (< 10 chars)", 0.5),
        (None, "None input", 0.5),
    ]

    edge_passed = 0
    edge_failed = []

    for text, description, expected in edge_cases:
        print(f"\nTest: {description}")
        score = analyze_semantic(text)
        status = "✓ PASS" if score == expected else "✗ FAIL"
        print(f"{status}: Got {score}, expected {expected}")

        if score == expected:
            edge_passed += 1
        else:
            edge_failed.append((description, expected, score))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    total_tests = len(test_texts) + len(edge_cases)
    total_passed = passed_count + edge_passed

    print(f"\nSemantic Tests: {passed_count}/{len(test_texts)} passed")
    print(f"Edge Case Tests: {edge_passed}/{len(edge_cases)} passed")
    print(f"Total: {total_passed}/{total_tests} passed")

    if failed_tests:
        print(f"\n⚠ Tests Outside Expected Range ({len(failed_tests)}):")
        for name, expected_range, got in failed_tests:
            print(f"  - {name}: expected {expected_range}, got {got:.2f}")

    if edge_failed:
        print(f"\n✗ Failed Edge Case Tests ({len(edge_failed)}):")
        for desc, expected, got in edge_failed:
            print(f"  - {desc}: expected {expected}, got {got}")

    print("\n" + "=" * 60)
    if total_passed == total_tests:
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return True
    else:
        print(f"⚠ {total_tests - total_passed} TESTS OUTSIDE EXPECTED RANGE")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = test_groq_analyzer()
    exit(0 if success else 1)
