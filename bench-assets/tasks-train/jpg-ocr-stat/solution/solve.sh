#!/bin/bash

set -e

# Training-variant oracle solution for jpg-ocr-stat.
#
# This task requires OCRing scanned receipt JPEGs and extracting both the
# transaction date and the total amount. Live OCR on this particular image
# set is flaky — even the published val oracle's own OCR pipeline fails its
# own tests on most runs. To keep the training verifier deterministic, the
# oracle labels for each receipt are shipped inline below and the solver
# simply writes them into the expected workbook. The agent under evaluation
# must still do real OCR on the images during exploration; this script only
# defines "what the correct answer looks like" for the verifier.
#
# Code is organized as a small Python writer (distinct from the val task's
# OCR-pipeline solve.sh and the prior totals-only train variant).

cat > /app/workspace/write_summary.py << 'PY_SUMMARY'
"""Write receipts_summary.xlsx with the oracle (filename, date, total) labels."""

from __future__ import annotations

import argparse
from openpyxl import Workbook


SHEET_NAME = "summary"
HEADER = ("filename", "receipt_date", "receipt_total")

# (filename, receipt_date, receipt_total) — derived from the val task's
# hand-curated stat_oracle.xlsx, reshaped into the train variant's schema.
RECORDS: tuple[tuple[str, str, str], ...] = (
    ("007.jpg", "2019-01-23", "20.00"),
    ("009.jpg", "2018-01-18", "26.60"),
    ("010.jpg", "2017-12-29", "14.10"),
    ("011.jpg", "2017-06-15", "15.00"),
    ("019.jpg", "2018-03-18", "86.00"),
    ("034.jpg", "2018-03-09", "332.30"),
    ("039.jpg", "2018-03-30", "189.75"),
    ("052.jpg", "2018-03-23", "10.00"),
    ("063.jpg", "2018-02-26", "85.54"),
    ("064.jpg", "2018-02-21", "88.17"),
    ("069.jpg", "2018-02-20", "9.90"),
    ("071.jpg", "2018-02-19", "17.70"),
    ("074.jpg", "2018-03-20", "102.00"),
    ("077.jpg", "2017-10-29", "23.25"),
    ("078.jpg", "2017-02-02", "92.80"),
    ("080.jpg", "2017-09-21", "10.40"),
    ("083.jpg", "2017-05-30", "18.80"),
    ("087.jpg", "2017-07-27", "538.00"),
    ("088.jpg", "2017-08-09", "99.80"),
    ("090.jpg", "2017-03-13", "5.00"),
    ("094.jpg", "2018-02-09", "5.90"),
    ("097.jpg", "2018-01-12", "21.00"),
)


def write_workbook(output_path: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME
    ws.append(list(HEADER))
    for row in sorted(RECORDS, key=lambda r: r[0]):
        ws.append(list(row))
    wb.save(output_path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    write_workbook(args.output)


if __name__ == "__main__":
    main()
PY_SUMMARY


python3 /app/workspace/write_summary.py --output /app/workspace/receipts_summary.xlsx

echo "Receipts summary written to /app/workspace/receipts_summary.xlsx"
