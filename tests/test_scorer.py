"""
Test suite for scorer.py (Confidence scoring function)

No API key required - tests the weighted ensemble formula locally.

Run from project root with:
    python3 -m pytest tests/test_scorer.py

Or run directly from tests folder with:
    python3 test_scorer.py
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import detection modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from detection.scorer import score_confidence


def test_scorer():
    print("=" * 60)
    print("SCORER FUNCTION TESTS")
    print("=" * 60)

    # Test cases: (signal_1, signal_2, expected, description)
    # Formula: (0.70 × signal_1) + (0.30 × signal_2)
    test_cases = [
        (0.0, 0.0, 0.0, "Both signals AI-like"),
        (1.0, 1.0, 1.0, "Both signals human-like"),
        (0.5, 0.5, 0.5, "Both signals uncertain"),
        (0.8, 0.2, 0.62, "Signal 1 high, Signal 2 low"),
        (0.2, 0.8, 0.38, "Signal 1 low, Signal 2 high"),
        (0.65, 0.50, 0.605, "Example from spec"),
        (0.0, 1.0, 0.30, "Extreme disagreement 1"),
        (1.0, 0.0, 0.70, "Extreme disagreement 2"),
    ]

    passed_count = 0
    failed_tests = []

    for signal_1, signal_2, expected, description in test_cases:
        result = score_confidence(signal_1, signal_2)
        passed = abs(result - expected) < 0.001  # Allow for floating point precision
        status = "✓ PASS" if passed else "✗ FAIL"

        print(f"\n{status}: {description}")
        print(f"  Input: signal_1={signal_1}, signal_2={signal_2}")
        print(f"  Expected: {expected}")
        print(f"  Got: {result}")

        if passed:
            passed_count += 1
        else:
            failed_tests.append((description, expected, result))

    # Threshold verification tests
    print("\n" + "=" * 60)
    print("THRESHOLD VERIFICATION")
    print("=" * 60)

    threshold_tests = [
        (0.10, "< 0.20", "High-confidence AI"),
        (0.50, "0.20-0.80", "Uncertain"),
        (0.90, "> 0.80", "High-confidence human"),
    ]

    threshold_passed = 0
    threshold_failed = []

    for confidence, expected_range, label in threshold_tests:
        # For demo, just use confidence as-is (same signal values)
        result = score_confidence(confidence, confidence)

        if expected_range == "< 0.20":
            passed = result < 0.20
        elif expected_range == "0.20-0.80":
            passed = 0.20 <= result <= 0.80
        elif expected_range == "> 0.80":
            passed = result > 0.80

        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"\n{status}: {label} ({expected_range})")
        print(f"  Score: {result}")

        if passed:
            threshold_passed += 1
        else:
            threshold_failed.append((label, expected_range, result))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    total_tests = len(test_cases) + len(threshold_tests)
    total_passed = passed_count + threshold_passed

    print(f"\nFormula Tests: {passed_count}/{len(test_cases)} passed")
    print(f"Threshold Tests: {threshold_passed}/{len(threshold_tests)} passed")
    print(f"Total: {total_passed}/{total_tests} passed")

    if failed_tests:
        print(f"\n✗ Failed Formula Tests ({len(failed_tests)}):")
        for desc, expected, got in failed_tests:
            print(f"  - {desc}: expected {expected}, got {got}")

    if threshold_failed:
        print(f"\n✗ Failed Threshold Tests ({len(threshold_failed)}):")
        for label, expected_range, got in threshold_failed:
            print(f"  - {label}: expected {expected_range}, got {got}")

    print("\n" + "=" * 60)
    if total_passed == total_tests:
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return True
    else:
        print(f"✗ {total_tests - total_passed} TESTS FAILED")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = test_scorer()
    exit(0 if success else 1)
