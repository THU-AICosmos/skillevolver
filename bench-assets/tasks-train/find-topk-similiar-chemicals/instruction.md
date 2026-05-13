Find the top N most structurally similar compounds in `compounds.pdf` to any query compound you are given.

For resolving compound names to molecular structures, use an external chemistry resource such as PubChem or RDKit. For measuring structural similarity, compute Morgan fingerprints with Tanimoto coefficient (radius = 2, include chirality). Results should be sorted in descending order of similarity, using alphabetical name ordering to break ties.

Write your solution to `/root/workspace/finder.py`. You must implement a Python function `find_nearest_compounds(query_name, compounds_pdf_path, n) -> list`. You must not hard-code any chemical name to SMILES mappings.
