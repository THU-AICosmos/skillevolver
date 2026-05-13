#!/bin/bash
# Solution script: Write solution.py to /root/workspace/

set -e

mkdir -p /root/workspace

cat > /root/workspace/solution.py << 'SOLEOF'
#!/usr/bin/env python3
"""
Extracts site symmetry multiplicities and representative fractional
coordinates from CIF files using pymatgen symmetry tools and sympy rationals.
"""

from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from collections import Counter, defaultdict
from sympy import Rational


def _coord_to_fraction(val, max_denom=12):
    """Convert a float coordinate to a string fraction with bounded denominator."""
    r = Rational(val).limit_denominator(max_denom)
    return str(r)


def extract_site_symmetry_and_fractional_positions(cif_path: str) -> dict:
    """
    Parse a CIF file, determine Wyckoff site letters via spglib,
    then return multiplicities and the first atom's coordinates per letter.
    """
    crystal = Structure.from_file(cif_path)
    analyzer = SpacegroupAnalyzer(crystal)
    sym_data = analyzer.get_symmetry_dataset()

    if sym_data is None:
        return {"site_multiplicities": {}, "representative_coords": {}}

    letters = sym_data.wyckoffs

    # Tally how many atoms share each Wyckoff letter
    counts = dict(sorted(Counter(letters).items()))

    # Group sites by letter and pick the first representative
    grouped = defaultdict(list)
    for idx, s in enumerate(crystal):
        grouped[letters[idx]].append(s)

    coords_map = {}
    for ltr in sorted(grouped):
        first_site = grouped[ltr][0]
        frac = first_site.frac_coords
        coords_map[ltr] = [_coord_to_fraction(c) for c in frac]

    return {
        "site_multiplicities": counts,
        "representative_coords": coords_map,
    }
SOLEOF

echo "Solution written to /root/workspace/solution.py"
