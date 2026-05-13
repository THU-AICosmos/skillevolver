You are a computational crystallographer working on a batch analysis pipeline. You have a collection of CIF files representing common inorganic crystal structures obtained from X-ray diffraction refinement.

Your goal is to build a Python function that, for each CIF file, determines the **site multiplicities** for each distinct Wyckoff letter and extracts the **representative fractional coordinates** (of the first atom belonging to each Wyckoff position).

The entry function should be:
```
    def extract_site_symmetry_and_fractional_positions(cif_path: str) -> dict[str, dict]
```

An example output for a hypothetical cubic structure might look like:
```
    {
        "site_multiplicities": {"a": 4, "c": 8},
        "representative_coords": {
            "a": ["0", "0", "0"],
            "c": ["1/4", "1/4", "1/4"]
        }
    }
```

** Important **

Write your script at: /root/workspace/solution.py

- Use appropriate Python libraries for reading CIF data, performing symmetry analysis, and converting floating-point coordinates to rational fractions.
- Fractional coordinate denominators must be limited to 12 or less.
- Results must be sorted alphabetically by Wyckoff letter.
- Do not hardcode any answers in your script.
