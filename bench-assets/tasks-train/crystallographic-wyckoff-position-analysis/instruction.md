You are a mineralogist studying the symmetry properties of crystalline materials. You have a collection of CIF files obtained from powder diffraction experiments and need to perform a batch symmetry analysis.

Your task is to build a Python function that, for each CIF file, determines the space group number, counts atoms per Wyckoff position, and computes the centroid (mean fractional coordinate) of all atoms within each Wyckoff group.

The entry function should look like:
```
    def analyze_spacegroup_and_wyckoff_centroids(filepath: str) -> dict[str, Any]
```

An example output using input "/root/cif_files/FeS2_mp-226.cif" (datasource: https://next-gen.materialsproject.org/) shall look like as follows in dict format (for fractions, constrain fractions to have denominators ≤ 10 for a simpler result):
```
    {
        "space_group_number": 205,
        "wyckoff_atom_count": {"a": 4, "c": 8},
        "wyckoff_centroid_coords": {
            "a": ["1/4", "1/4", "1/4"],
            "c": ["2/5", "1/2", "1/2"]
        }
    }
```

** Important **

Write your script at: /root/workspace/solution.py

You are encouraged to use external imports for CIF file reading, space group analysis, and coordinate calculations.
You must not hardcode answers within your script.

The centroid coordinates should be computed as the arithmetic mean of all fractional coordinates of atoms sharing the same Wyckoff letter, then rounded to the closest rational number format with denominator ≤ 10, as shown in the example output.
