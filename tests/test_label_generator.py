"""
Test suite for label_generator.py

Tests the mapping of confidence scores to classifications and labels.

Run from project root with:
    python3 tests/test_label_generator.py

Or run directly from tests folder with:
    python3 test_label_generator.py
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import labels module
sys.path.insert(0, str(Path(__file__).parent.parent))

from labels.generator import generate_label, get_classification, get_label_text


def test_label_generator():
    print("=" * 60)
    print("LABEL GENERATOR TESTS")
    print("=" * 60)

    # Test cases: (confidence, expected_classification, description)
    test_cases = [
        (0.10, "ai", "Low confidence AI"),
        (0.34, "ai", "Boundary: just below 0.35"),
        (0.35, "uncertain", "Boundary: exactly 0.35"),
        (0.50, "uncertain", "Middle uncertainty"),
        (0.70, "uncertain", "Boundary: exactly 0.70"),
        (0.71, "human", "Boundary: just above 0.70"),
        (0.90, "human", "High confidence human"),
    ]

    passed_count = 0
    failed_tests = []

    for confidence, expected_class, description in test_cases:
        result = generate_label(confidence)
        classification = result["classification"]
        label = result["label"]

        passed = classification == expected_class
        status = "✓ PASS" if passed else "✗ FAIL"

        print(f"\n{status}: {description}")
        print(f"  Input: {confidence}")
        print(f"  Expected classification: {expected_class}")
        print(f"  Got classification: {classification}")
        print(f"  Label: {label[:60]}...")

        if passed:
            passed_count += 1
        else:
            failed_tests.append((description, expected_class, classification))

    # Label text verification
    print("\n" + "=" * 60)
    print("LABEL TEXT VERIFICATION")
    print("=" * 60)

    label_tests = [
        (0.10, "AI-generated content"),
        (0.50, "uncertain about the origin"),
        (0.80, "written by a human"),
    ]

    label_passed = 0
    label_failed = []

    for confidence, expected_phrase in label_tests:
        label = get_label_text(confidence)
        contains_phrase = expected_phrase.lower() in label.lower()
        status = "✓ PASS" if contains_phrase else "✗ FAIL"

        print(f"\n{status}: Confidence {confidence}")
        print(f"  Looking for: '{expected_phrase}'")
        print(f"  Got: '{label}'")

        if contains_phrase:
            label_passed += 1
        else:
            label_failed.append((confidence, expected_phrase, label))

    # Helper function tests
    print("\n" + "=" * 60)
    print("HELPER FUNCTION TESTS")
    print("=" * 60)

    helper_tests = [
        (0.05, "ai"),
        (0.50, "uncertain"),
        (0.95, "human"),
    ]

    helper_passed = 0
    helper_failed = []

    for confidence, expected in helper_tests:
        classification = get_classification(confidence)
        passed = classification == expected
        status = "✓ PASS" if passed else "✗ FAIL"

        print(f"\n{status}: get_classification({confidence}) → {classification}")

        if passed:
            helper_passed += 1
        else:
            helper_failed.append((confidence, expected, classification))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    total_classification = len(test_cases)
    total_label = len(label_tests)
    total_helper = len(helper_tests)
    total_tests = total_classification + total_label + total_helper

    total_passed = passed_count + label_passed + helper_passed

    print(f"\nClassification Tests: {passed_count}/{total_classification} passed")
    print(f"Label Text Tests: {label_passed}/{total_label} passed")
    print(f"Helper Function Tests: {helper_passed}/{total_helper} passed")
    print(f"Total: {total_passed}/{total_tests} passed")

    if failed_tests:
        print(f"\n✗ Failed Classification Tests ({len(failed_tests)}):")
        for desc, expected, got in failed_tests:
            print(f"  - {desc}: expected {expected}, got {got}")

    if label_failed:
        print(f"\n✗ Failed Label Text Tests ({len(label_failed)}):")
        for conf, phrase, got in label_failed:
            print(f"  - Confidence {conf}: expected '{phrase}', got '{got}'")

    if helper_failed:
        print(f"\n✗ Failed Helper Tests ({len(helper_failed)}):")
        for conf, expected, got in helper_failed:
            print(f"  - get_classification({conf}): expected {expected}, got {got}")

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
    success = test_label_generator()
    exit(0 if success else 1)
