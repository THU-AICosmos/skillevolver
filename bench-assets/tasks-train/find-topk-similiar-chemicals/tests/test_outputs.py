#!/usr/bin/env python3
"""
Test script for pharmaceutical compound similarity search
Validates that the solution produces correct top K similar compounds
"""

import sys
import os
import pytest

# Add workspace to path
sys.path.insert(0, '/root/workspace')

# Import the solution function
from solution import topk_tanimoto_similarity_molecules


# Expected results based on testing
# Caffeine: top 15, Cholesterol: top 8 (to reduce possibility of guessing)
EXPECTED_RESULTS = {
    'Caffeine': {
        'top_k': 15,
        'molecules': [
            'Caffeine',
            'Theobromine',
            'Theophylline',
            'Guanine',
            'Phenobarbital',
            'Uracil',
            'Riboflavin',
            'Diazepam',
            'Pyridoxine',
            'Thymol',
            'Omeprazole',
            'Thiamine',
            'Doxycycline',
            'Propofol',
            'Lidocaine'
        ]
    },
    'Cholesterol': {
        'top_k': 8,
        'molecules': [
            'Cholesterol',
            'Testosterone',
            'Progesterone',
            'Hydrocortisone',
            'Cortisone',
            'Prednisone',
            'Menthol',
            'Simvastatin'
        ]
    }
}

PDF_PATH = '/root/compounds.pdf'  # Path to compounds PDF in container


@pytest.mark.parametrize("molecule,top_k,expected", [
    ('Caffeine', EXPECTED_RESULTS['Caffeine']['top_k'], EXPECTED_RESULTS['Caffeine']['molecules']),
    ('Cholesterol', EXPECTED_RESULTS['Cholesterol']['top_k'], EXPECTED_RESULTS['Cholesterol']['molecules']),
])
def test_molecule_similarity(molecule, top_k, expected):
    """Test that compound similarity ranking returns correct top K results"""
    print("\n" + "="*70)
    print(f"TEST: {molecule} Similarity Search (top {top_k})")
    print("="*70)

    result = topk_tanimoto_similarity_molecules(molecule, PDF_PATH, top_k=top_k)

    print(f"\nExpected ({top_k}): {expected}")
    print(f"Got:      {result}")

    # Check that result has correct number of molecules
    assert len(result) == top_k, f"Expected {top_k} compounds for {molecule}, got {len(result)}"

    # Check that all expected molecules are in the result
    for mol in expected:
        assert mol in result, f"Expected compound '{mol}' not found in {molecule} results"

    # Check exact order
    assert result == expected, f"Order mismatch for {molecule}. Expected {expected}, got {result}"

    print(f"\n✓ {molecule} test PASSED")


def calculate_score():
    """
    Calculate test score: passed_tests / total_tests
    """
    # Test cases with parameterized inputs
    test_cases = [
        ('Caffeine', EXPECTED_RESULTS['Caffeine']['top_k'], EXPECTED_RESULTS['Caffeine']['molecules']),
        ('Cholesterol', EXPECTED_RESULTS['Cholesterol']['top_k'], EXPECTED_RESULTS['Cholesterol']['molecules']),
    ]

    total_tests = len(test_cases)
    passed_tests = 0

    for molecule, top_k, expected in test_cases:
        print("\n" + "="*70)
        print(f"Running {molecule} test...")
        print("="*70)
        try:
            test_molecule_similarity(molecule, top_k, expected)
            passed_tests += 1
            print(f"[PASSED] {molecule} test")
        except Exception as e:
            print(f"[FAILED] {molecule} test: {e}")

    # Calculate score
    score = passed_tests / total_tests

    print("\n" + "="*70)
    print(f"FINAL SCORE: {passed_tests}/{total_tests} = {score}")
    print("="*70)

    # Write score to reward file
    os.makedirs('/logs/verifier', exist_ok=True)
    with open('/logs/verifier/reward.txt', 'w') as f:
        f.write(f"{score}\n")

    return score


if __name__ == "__main__":
    # Run the scoring function directly
    score = calculate_score()

    # Exit with appropriate code
    if score == 1.0:
        sys.exit(0)
    else:
        sys.exit(1)
