#!/usr/bin/env python3
"""
Test suite for crystal symmetry and Wyckoff centroid analysis using pymatgen and sympy.

Tests the analyze_spacegroup_and_wyckoff_centroids() function
against known results from crystallographic CIF files.
"""

import sys
import os
import pytest
from pathlib import Path

# Add workspace to path
sys.path.insert(0, '/root/workspace')

from solution import analyze_spacegroup_and_wyckoff_centroids


# Expected results for each CIF file
EXPECTED_RESULTS = {
    "Al2O3_mp-7048.cif": {
        'space_group_number': 12,
        'wyckoff_atom_count': {'i': 20},
        'wyckoff_centroid_coords': {'i': ['1/2', '1/4', '1/2']}
    },
    "C_mp-169.cif": {
        'space_group_number': 12,
        'wyckoff_atom_count': {'i': 4},
        'wyckoff_centroid_coords': {'i': ['1/2', '1/4', '1/2']}
    },
    "CF4_mp-1167.cif": {
        'space_group_number': 15,
        'wyckoff_atom_count': {'e': 4, 'f': 16},
        'wyckoff_centroid_coords': {'e': ['1/4', '1/2', '1/2'], 'f': ['1/2', '1/2', '1/2']}
    },
    "FeS2_mp-1522.cif": {
        'space_group_number': 58,
        'wyckoff_atom_count': {'a': 2, 'g': 4},
        'wyckoff_centroid_coords': {'a': ['1/4', '1/4', '1/4'], 'g': ['1/4', '1/2', '1/2']}
    },
    "FeS2_mp-226.cif": {
        'space_group_number': 205,
        'wyckoff_atom_count': {'a': 4, 'c': 8},
        'wyckoff_centroid_coords': {'a': ['1/4', '1/4', '1/4'], 'c': ['1/2', '1/2', '1/2']}
    },
    "HgSe_mp-1018722.cif": {
        'space_group_number': 154,
        'wyckoff_atom_count': {'a': 3, 'b': 3},
        'wyckoff_centroid_coords': {'a': ['1/3', '1/3', '1/3'], 'b': ['1/3', '1/3', '1/2']}
    },
    "SiO2_mp-6945.cif": {
        'space_group_number': 92,
        'wyckoff_atom_count': {'a': 4, 'b': 8},
        'wyckoff_centroid_coords': {'a': ['1/2', '1/2', '3/8'], 'b': ['1/2', '1/2', '1/2']}
    },
    "SiO2_mp-7000.cif": {
        'space_group_number': 152,
        'wyckoff_atom_count': {'a': 3, 'c': 6},
        'wyckoff_centroid_coords': {'a': ['1/3', '1/3', '1/3'], 'c': ['1/2', '1/2', '1/2']}
    }
}


CIF_DIR = Path("/root/cif_files")


@pytest.mark.parametrize("filename,expected", list(EXPECTED_RESULTS.items()))
def test_spacegroup_and_centroids(filename, expected):
    """Test that analysis matches expected results for each CIF file."""
    cif_path = CIF_DIR / filename
    result = analyze_spacegroup_and_wyckoff_centroids(str(cif_path))
    assert result == expected, f"Mismatch for {filename}:\nExpected: {expected}\nGot: {result}"


def main():
    """Run tests and generate reward score."""
    total_tests = 0
    passed_tests = 0
    failed_tests = []

    print("=" * 80)
    print("Testing Crystal Symmetry and Wyckoff Centroid Analysis")
    print("=" * 80)

    for filename, expected in EXPECTED_RESULTS.items():
        total_tests += 1
        cif_path = CIF_DIR / filename

        print(f"\nTest {total_tests}: {filename}")
        print("-" * 80)

        try:
            result = analyze_spacegroup_and_wyckoff_centroids(str(cif_path))

            if result == expected:
                print(f"✓ PASSED")
                passed_tests += 1
            else:
                print(f"✗ FAILED")
                print(f"  Expected: {expected}")
                print(f"  Got:      {result}")
                failed_tests.append(filename)

        except Exception as e:
            print(f"✗ FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            failed_tests.append(filename)

    # Summary
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")

    if failed_tests:
        print(f"\nFailed tests: {', '.join(failed_tests)}")

    score = passed_tests / total_tests if total_tests > 0 else 0.0
    print(f"\nScore: {score:.2f}")

    os.makedirs('/logs/verifier', exist_ok=True)
    with open('/logs/verifier/reward.txt', 'w') as f:
        f.write(f"{score:.2f}\n")

    return 0


if __name__ == '__main__':
    exit(main())
