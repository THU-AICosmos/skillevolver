#!/bin/bash
# Solution script: Write finder.py to /root/workspace/
# Note: relies on PubChem web service; may partially fail under heavy load.

set -e

mkdir -p /root/workspace

cat > /root/workspace/finder.py << 'PYCODE'
#!/usr/bin/env python3
"""
Compound Structural Similarity Finder
Resolves names via PubChem, computes Morgan fingerprints, ranks by Tanimoto.
"""

import pdfplumber
import pubchempy as pcp
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit import DataStructs
from rdkit import RDLogger
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

RDLogger.DisableLog('rdApp.*')

_rate_limiter = threading.Semaphore(5)


class CompoundRecord:
    """Holds name + computed similarity."""
    __slots__ = ('name', 'score')
    def __init__(self, name, score):
        self.name = name
        self.score = score


def _resolve_and_score(compound_name, reference_fp, attempts=5):
    """Look up a compound in PubChem, compute Tanimoto vs reference fingerprint."""
    err = None
    for trial in range(attempts):
        with _rate_limiter:
            try:
                time.sleep(0.1 * (trial + 1))
                hits = pcp.get_compounds(compound_name, 'name')
                if not hits:
                    return CompoundRecord(compound_name, None)
                mol = Chem.MolFromSmiles(hits[0].smiles)
                if mol is None:
                    return CompoundRecord(compound_name, None)
                fp = AllChem.GetMorganFingerprint(mol, 2, useChirality=True)
                score = DataStructs.TanimotoSimilarity(reference_fp, fp)
                return CompoundRecord(compound_name, score)
            except Exception as exc:
                err = exc
                if any(tok in str(exc) for tok in ("Timeout", "503", "504")):
                    continue
                return CompoundRecord(compound_name, None)
    return CompoundRecord(compound_name, None)


def _read_compound_names(pdf_path):
    """Extract one compound name per non-empty line from a PDF."""
    names = []
    with pdfplumber.open(pdf_path) as doc:
        for pg in doc.pages:
            raw = pg.extract_text()
            if not raw:
                continue
            for ln in raw.strip().split('\n'):
                ln = ln.strip()
                if ln and not ln.isdigit():
                    names.append(ln)
    return names


def find_nearest_compounds(query_name, compounds_pdf_path, n=10):
    """
    Return the n most structurally similar compounds to *query_name*
    from the pool listed in *compounds_pdf_path*.

    Similarity metric: Tanimoto coefficient on Morgan fingerprints
    (radius=2, chirality=True).

    Ties are broken alphabetically (ascending).
    """
    pool = _read_compound_names(compounds_pdf_path)
    if not pool:
        return []

    # Resolve query compound
    query_hits = pcp.get_compounds(query_name, 'name')
    if not query_hits:
        return []
    query_mol = Chem.MolFromSmiles(query_hits[0].smiles)
    if query_mol is None:
        return []
    query_fp = AllChem.GetMorganFingerprint(query_mol, 2, useChirality=True)

    # Score every compound in parallel
    records = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(_resolve_and_score, name, query_fp): name
            for name in pool
        }
        for fut in as_completed(futures):
            rec = fut.result()
            if rec.score is not None:
                records.append(rec)

    # Rank: highest similarity first, alphabetical on ties
    records.sort(key=lambda r: (-r.score, r.name))

    return [r.name for r in records[:n]]
PYCODE

echo "Solution written to /root/workspace/finder.py"
