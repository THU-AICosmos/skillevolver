#!/usr/bin/env python3
"""
Test script for compound structural similarity search.
Validates that the solution returns correct nearest N compounds.
"""

import sys
import os
import pytest

# Add workspace to path
sys.path.insert(0, '/root/workspace')

# Import the solution function
from finder import find_nearest_compounds


# Ground-truth rankings computed with PubChem + Morgan FP (radius=2, chirality) + Tanimoto
# Caffeine: top 15, Cholesterol: top 8
GROUND_TRUTH = {
    'Caffeine': {
        'n': 15,
        'ranking': [
            'Caffeine',
            'Theobromine',
            'Theophylline',
            'Thymine',
            'Guanine',
            'Meloxicam',
            'Piroxicam',
            'Cytosine',
            'Uracil',
            'Riboflavin',
            'Metronidazole',
            'Pyridoxine',
            'Sulfamethoxazole',
            'Omeprazole',
            'Trimethoprim',
        ]
    },
    'Cholesterol': {
        'n': 8,
        'ranking': [
            'Cholesterol',
            'Campesterol',
            'Stigmasterol',
            'Ergosterol',
            'Testosterone',
            'Progesterone',
            'Cortisol',
            'Estradiol',
        ]
    }
}

COMPOUNDS_PDF = '/root/compounds.pdf'  # Path to compounds PDF in container


@pytest.mark.parametrize("query,n,expected_ranking", [
    ('Caffeine', GROUND_TRUTH['Caffeine']['n'], GROUND_TRUTH['Caffeine']['ranking']),
    ('Cholesterol', GROUND_TRUTH['Cholesterol']['n'], GROUND_TRUTH['Cholesterol']['ranking']),
])
def test_nearest_compounds(query, n, expected_ranking):
    """Test that compound similarity search returns the correct nearest N compounds."""
    print("\n" + "=" * 70)
    print(f"TEST: {query} Nearest Compounds (n={n})")
    print("=" * 70)

    result = find_nearest_compounds(query, COMPOUNDS_PDF, n=n)

    print(f"\nExpected ({n}): {expected_ranking}")
    print(f"Got:      {result}")

    # Check length
    assert len(result) == n, f"Expected {n} compounds for {query}, got {len(result)}"

    # Check membership
    for cmpd in expected_ranking:
        assert cmpd in result, f"Expected compound '{cmpd}' not found in {query} results"

    # Check ordering
    assert result == expected_ranking, (
        f"Order mismatch for {query}. Expected {expected_ranking}, got {result}"
    )

    print(f"\n[OK] {query} test PASSED")


def compute_reward():
    """
    Compute test reward: passed_tests / total_tests
    """
    cases = [
        ('Caffeine', GROUND_TRUTH['Caffeine']['n'], GROUND_TRUTH['Caffeine']['ranking']),
        ('Cholesterol', GROUND_TRUTH['Cholesterol']['n'], GROUND_TRUTH['Cholesterol']['ranking']),
    ]

    total = len(cases)
    passed = 0

    for query, n, expected_ranking in cases:
        print("\n" + "=" * 70)
        print(f"Running {query} test...")
        print("=" * 70)
        try:
            test_nearest_compounds(query, n, expected_ranking)
            passed += 1
            print(f"[PASSED] {query} test")
        except Exception as exc:
            print(f"[FAILED] {query} test: {exc}")

    reward = passed / total

    print("\n" + "=" * 70)
    print(f"FINAL REWARD: {passed}/{total} = {reward}")
    print("=" * 70)

    os.makedirs('/logs/verifier', exist_ok=True)
    with open('/logs/verifier/reward.txt', 'w') as fh:
        fh.write(f"{reward}\n")

    return reward


if __name__ == "__main__":
    reward = compute_reward()
    sys.exit(0 if reward == 1.0 else 1)
