"""
Module 4: Final Calibration Test

Test the complete scoring pipeline with 4 deliberately chosen inputs to verify
the system's intuition matches expected results.

Inputs:
1. Clearly AI-generated (corporate jargon, formulaic structure)
2. Clearly human-written (casual, authentic voice, typos)
3. Borderline: formal human writing (academic but genuine)
4. Borderline: lightly edited AI output (mixed signals)

Run from project root with:
    python3 tests/test_module4_calibration.py

Requires GROQ_API_KEY in .env file.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load GROQ_API_KEY from .env file if available
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

from detection.groq_analyzer import analyze_semantic
from detection.text_stats import calculate_text_statistics
from detection.scorer import score_confidence
from labels.generator import generate_label


def run_calibration_test():
    print("=" * 80)
    print("MODULE 4: FINAL CALIBRATION TEST")
    print("Testing scoring pipeline with 4 deliberately chosen inputs")
    print("=" * 80)

    # Check API key
    if not os.getenv("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY not set")
        print("Add it to .env file in project root:")
        print('  GROQ_API_KEY=your-key-here')
        return False

    # Test cases with expected score ranges
    test_cases = [
        {
            "name": "Clearly AI-generated",
            "text": """Artificial intelligence represents a transformative paradigm shift in modern society.
It is important to note that while the benefits of AI are numerous, it is equally
essential to consider the ethical implications. Furthermore, stakeholders across
various sectors must collaborate to ensure responsible deployment.""",
            "expected_classification": "ai",
            "expected_range": (0.0, 0.35),
            "reason": "Corporate jargon, formulaic structure, vague phrases"
        },
        {
            "name": "Clearly human-written",
            "text": """ok so i finally tried that new ramen place downtown and honestly?
underwhelming. the broth was fine but they put WAY too much sodium in it and
i was thirsty for like three hours after. my friend got the spicy version and
said it was better. probably won't go back unless someone drags me there""",
            "expected_classification": "human",
            "expected_range": (0.70, 1.0),
            "reason": "Casual tone, authentic voice, personal experience, imperfections"
        },
        {
            "name": "Borderline: formal human writing",
            "text": """The relationship between monetary policy and asset price inflation has been
extensively studied in the literature. Central banks face a fundamental tension
between their mandate for price stability and the unintended consequences of
prolonged low interest rates on equity and real estate valuations.""",
            "expected_classification": "uncertain",
            "expected_range": (0.40, 0.70),
            "reason": "Formal but genuine analysis, no corporate jargon, coherent reasoning"
        },
        {
            "name": "Borderline: lightly edited AI output",
            "text": """I've been thinking a lot about remote work lately. There are genuine tradeoffs —
flexibility and no commute on one side, isolation and blurred work-life boundaries
on the other. Studies show productivity varies widely by individual and role type.""",
            "expected_classification": "uncertain",
            "expected_range": (0.40, 0.70),
            "reason": "Personal voice but structured reasoning; mixed signals"
        },
    ]

    print("\nNote: First test may take 5-10 seconds...\n")

    results = []
    passed_count = 0

    for i, test_case in enumerate(test_cases, 1):
        print("=" * 80)
        print(f"TEST {i}: {test_case['name']}")
        print("=" * 80)

        text = test_case['text']
        print(f"\nText:\n{text}\n")
        print(f"Expected: {test_case['expected_classification']} (range: {test_case['expected_range']})")
        print(f"Reason: {test_case['reason']}\n")

        try:
            # Get both signals
            print("Calculating signals...")
            signal_1 = analyze_semantic(text)
            signal_2 = calculate_text_statistics(text)

            print(f"  Signal 1 (Groq Semantic):    {signal_1:.2f}")
            print(f"  Signal 2 (Text Statistics):  {signal_2:.2f}")

            # Calculate confidence
            confidence = score_confidence(signal_1, signal_2)
            print(f"  Confidence Score:            {confidence:.2f}")

            # Generate label
            label_result = generate_label(confidence)
            classification = label_result["classification"]
            label = label_result["label"]

            print(f"\nClassification: {classification.upper()}")
            print(f"Label: {label}")

            # Check if in expected range
            low, high = test_case['expected_range']
            in_range = low <= confidence <= high
            matches_classification = classification == test_case['expected_classification']

            # Determine pass/fail
            if in_range and matches_classification:
                status = "✓ PASS"
                passed_count += 1
                intuition_match = "YES - matches intuition"
            elif in_range and not matches_classification:
                status = "⚠ PARTIAL"
                intuition_match = f"PARTIAL - in expected range but classification is '{classification}' not '{test_case['expected_classification']}'"
            else:
                status = "✗ FAIL"
                intuition_match = f"NO - scored {confidence:.2f}, expected {test_case['expected_range']}"

            print(f"\n{status}: {intuition_match}")

            results.append({
                "name": test_case['name'],
                "confidence": confidence,
                "classification": classification,
                "signal_1": signal_1,
                "signal_2": signal_2,
                "status": status,
                "expected_range": test_case['expected_range'],
                "expected_class": test_case['expected_classification']
            })

        except Exception as e:
            print(f"✗ ERROR: {e}")
            results.append({
                "name": test_case['name'],
                "error": str(e),
                "status": "✗ ERROR"
            })

        print()

    # Summary
    print("=" * 80)
    print("CALIBRATION TEST SUMMARY")
    print("=" * 80)

    print(f"\nResults: {passed_count}/{len(test_cases)} tests passed intuition check\n")

    # Detailed results table
    print("Test Results:")
    print("-" * 80)
    for result in results:
        if "error" in result:
            print(f"{result['status']} | {result['name']}: {result['error']}")
        else:
            print(f"{result['status']} | {result['name']}")
            print(f"       Confidence: {result['confidence']:.2f} | Expected range: {result['expected_range']}")
            print(f"       Signal 1: {result['signal_1']:.2f}, Signal 2: {result['signal_2']:.2f}")
            print(f"       Classification: {result['classification']} (expected: {result['expected_class']})")
        print()

    # Analysis
    print("=" * 80)
    print("ANALYSIS")
    print("=" * 80)

    if passed_count == len(test_cases):
        print("\n✓ All tests match intuition!")
        print("\nThe scoring pipeline is well-calibrated:")
        print("  - AI-generated text scores low")
        print("  - Human-written text scores high")
        print("  - Borderline cases fall in uncertain range")
        print("\nReady to move forward with full system integration.")
        return True
    else:
        print(f"\n⚠ {len(test_cases) - passed_count} test(s) need investigation")
        print("\nInvestigation guide:")
        print("  1. Check if Signal 1 and Signal 2 are in agreement")
        print("  2. If they disagree, understand what each is detecting")
        print("  3. Verify the prompt in groq_analyzer.py")
        print("  4. Check text_stats.py metrics (TTR, bigram, variance)")
        print("  5. Consider if the confidence thresholds need adjustment")
        return False


if __name__ == "__main__":
    success = run_calibration_test()
    exit(0 if success else 1)
