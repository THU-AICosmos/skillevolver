#!/bin/bash
set -e

cat > /tmp/inventory_compare.py << 'PYEOF'
#!/usr/bin/env python3
"""
Solve warehouse inventory diff: extract table from archived PDF,
compare with current Excel, report deletions and modifications.
"""

import json
import re
import pdfplumber
import pandas as pd
import numpy as np

ARCHIVE_PDF = "/root/inventory_archive.pdf"
CURRENT_XLS = "/root/inventory_current.xlsx"
REPORT_OUT  = "/root/inventory_diff.json"

NUMERIC_COLUMNS = {"UnitPrice": float, "Quantity": int}
CODE_PATTERN = re.compile(r"^PROD\d{4}$")


def parse_pdf_inventory(path):
    """Read every page of the archived PDF and return a DataFrame."""
    print(f"[pdf] opening {path}")
    rows, header = [], None
    with pdfplumber.open(path) as pdf:
        n_pages = len(pdf.pages)
        print(f"[pdf] {n_pages} pages")
        for pg_idx, page in enumerate(pdf.pages):
            if pg_idx % 20 == 0:
                print(f"[pdf] page {pg_idx+1}/{n_pages}")
            for tbl in page.extract_tables():
                if not tbl:
                    continue
                for raw_row in tbl:
                    if not raw_row or all(c is None or str(c).strip() == "" for c in raw_row):
                        continue
                    cells = [str(c).strip() if c else "" for c in raw_row]
                    if header is None and cells[0] == "Code":
                        header = cells
                        continue
                    if header and CODE_PATTERN.match(cells[0]):
                        rows.append(cells)
    print(f"[pdf] extracted {len(rows)} product rows")
    df = pd.DataFrame(rows, columns=header)
    for col, cast in NUMERIC_COLUMNS.items():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_excel_inventory(path):
    """Load the current inventory from an xlsx file."""
    print(f"[xls] reading {path}")
    df = pd.read_excel(path)
    print(f"[xls] {len(df)} rows")
    return df


def build_diff(df_old, df_new):
    """Return dict with deleted_products and modified_products."""
    old_ids = set(df_old["Code"])
    new_ids = set(df_new["Code"])

    removed = sorted(old_ids - new_ids)
    print(f"[diff] {len(removed)} products removed")

    shared = sorted(old_ids & new_ids)
    old_ix = df_old.set_index("Code")
    new_ix = df_new.set_index("Code")

    changes = []
    for pid in shared:
        r_old = old_ix.loc[pid]
        r_new = new_ix.loc[pid]
        for col in df_old.columns:
            if col == "Code":
                continue
            v_old = r_old[col]
            v_new = r_new[col]
            if pd.isna(v_old) and pd.isna(v_new):
                continue
            # normalise numpy scalars
            v_old = _native(v_old, col)
            v_new = _native(v_new, col)
            if v_old != v_new:
                changes.append({"id": pid, "field": col,
                                "old_value": v_old, "new_value": v_new})

    changes.sort(key=lambda m: (m["id"], m["field"]))
    print(f"[diff] {len(changes)} field-level modifications")
    return {"deleted_products": removed, "modified_products": changes}


def _native(val, col):
    """Convert a value to a plain Python type suitable for JSON."""
    if isinstance(val, (np.integer,)):
        val = int(val)
    elif isinstance(val, (np.floating,)):
        val = float(val)
    if isinstance(val, float):
        if col in NUMERIC_COLUMNS and NUMERIC_COLUMNS[col] is int and val == int(val):
            return int(val)
        return round(val, 2)
    return val


if __name__ == "__main__":
    df_archive = parse_pdf_inventory(ARCHIVE_PDF)
    df_current = load_excel_inventory(CURRENT_XLS)
    report = build_diff(df_archive, df_current)
    with open(REPORT_OUT, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"[done] report written to {REPORT_OUT}")
    print(f"       deletions : {len(report['deleted_products'])}")
    print(f"       modifications: {len(report['modified_products'])}")
PYEOF

python3 /tmp/inventory_compare.py
echo "Inventory comparison complete."
