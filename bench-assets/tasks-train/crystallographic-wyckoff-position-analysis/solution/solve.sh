#!/bin/bash
# Solution script: Write solution.py to /root/workspace/

set -e

mkdir -p /root/workspace

cat > /root/workspace/solution.py << 'EOF'
#!/usr/bin/env python3
"""
Solution for Crystal Symmetry and Wyckoff Centroid Analysis.
Analyzes space group numbers, Wyckoff atom counts, and centroid coordinates using pymatgen and sympy.
"""

from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from collections import Counter, defaultdict
from sympy import Rational
import numpy as np


def analyze_spacegroup_and_wyckoff_centroids(filepath: str):
    """
    Analyze crystal symmetry: space group number, Wyckoff atom counts,
    and centroid coordinates for each Wyckoff group.

    Args:
        filepath: Path to the CIF file

    Returns:
        dict with space_group_number, wyckoff_atom_count, wyckoff_centroid_coords
    """
    # Load structure from CIF
    structure = Structure.from_file(filepath)

    # Get symmetry analyzer
    sga = SpacegroupAnalyzer(structure)

    # Get space group number
    sg_number = sga.get_space_group_number()

    # Get symmetry dataset with Wyckoff information
    dataset = sga.get_symmetry_dataset()

    if dataset is None:
        return {
            'space_group_number': sg_number,
            'wyckoff_atom_count': {},
            'wyckoff_centroid_coords': {}
        }

    # Get Wyckoff letters for each atom
    wyckoff_letters = dataset.wyckoffs

    # Count atoms per Wyckoff position
    wyckoff_counts = Counter(wyckoff_letters)
    atom_count_dict = dict(sorted(wyckoff_counts.items()))

    # Group fractional coordinates by Wyckoff letter
    wyckoff_coords = defaultdict(list)
    for i, site in enumerate(structure):
        letter = wyckoff_letters[i]
        wyckoff_coords[letter].append(site.frac_coords)

    # Compute centroid for each Wyckoff group
    centroid_dict = {}
    for letter in sorted(wyckoff_coords.keys()):
        coords_list = wyckoff_coords[letter]
        # Compute mean of all coordinates in this Wyckoff group
        mean_coords = np.mean(coords_list, axis=0)

        # Convert to exact fractions using sympy with denominator limit 10
        exact = []
        for c in mean_coords:
            rat = Rational(c).limit_denominator(10)
            exact.append(str(rat))

        centroid_dict[letter] = exact

    return {
        'space_group_number': sg_number,
        'wyckoff_atom_count': atom_count_dict,
        'wyckoff_centroid_coords': centroid_dict
    }
EOF

echo "Solution written to /root/workspace/solution.py"
