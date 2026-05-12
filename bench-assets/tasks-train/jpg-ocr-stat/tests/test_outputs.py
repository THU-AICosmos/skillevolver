"""
Use this file to define pytest tests that verify the outputs of the task.

This file will be copied to /tests/test_outputs.py and run by the /tests/test.sh file
from the working directory.
"""

import os
from typing import Any

from openpyxl import load_workbook


def _cell_to_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _read_sheet_as_rows(path: str, sheet_name: str):
    wb = load_workbook(path, data_only=True)
    try:
        ws = wb[sheet_name]
        max_row = ws.max_row or 0
        max_col = ws.max_column or 0
        rows = []
        for r in range(1, max_row + 1):
            rows.append([_cell_to_string(ws.cell(row=r, column=c).value) for c in range(1, max_col + 1)])
        return rows
    finally:
        wb.close()


OUTPUT_FILE = "/app/workspace/receipt_dates.xlsx"


def test_file_exists():
    """Test that the output file exists at the required path."""
    assert os.path.exists(OUTPUT_FILE), "receipt_dates.xlsx not found at /app/workspace"


def test_single_sheet_named_dates():
    """Test that the workbook has exactly one sheet named 'dates'."""
    wb = load_workbook(OUTPUT_FILE, data_only=True)
    try:
        sheets = list(wb.sheetnames)
        assert len(sheets) == 1, f"Expected exactly 1 sheet, got {len(sheets)}: {sheets}"
        assert sheets[0] == "dates", f"Expected sheet named 'dates', got '{sheets[0]}'"
    finally:
        wb.close()


def test_header_row():
    """Test that the header row has the correct column names."""
    rows = _read_sheet_as_rows(OUTPUT_FILE, "dates")
    assert len(rows) >= 1, "Workbook is empty"
    expected_header = ["filename", "date"]
    assert rows[0] == expected_header, (
        f"Header mismatch.\nActual:   {rows[0]}\nExpected: {expected_header}"
    )


def test_row_count():
    """Test that all 22 images are represented in the output."""
    rows = _read_sheet_as_rows(OUTPUT_FILE, "dates")
    # header + 22 data rows
    data_rows = [r for r in rows[1:] if len(r) >= 1 and r[0].strip() != ""]
    assert len(data_rows) == 22, f"Expected 22 data rows, got {len(data_rows)}"


def test_filenames_ordered():
    """Test that data rows are ordered by filename."""
    rows = _read_sheet_as_rows(OUTPUT_FILE, "dates")
    data_rows = [r for r in rows[1:] if len(r) >= 1 and r[0].strip() != ""]
    filenames = [r[0] for r in data_rows]
    assert filenames == sorted(filenames), (
        f"Rows not ordered by filename.\nActual: {filenames}\nSorted: {sorted(filenames)}"
    )


def test_spot_check_dates():
    """Spot-check extracted dates for 8 specific receipts."""
    rows = _read_sheet_as_rows(OUTPUT_FILE, "dates")
    # Build a lookup from filename -> date
    date_lookup = {}
    for r in rows[1:]:
        if len(r) >= 2 and r[0].strip():
            date_lookup[r[0]] = r[1]

    # Expected dates for 8 specific images (~36% of 22)
    expected = {
        "007.jpg": "2019-01-23",
        "011.jpg": "2017-06-15",
        "034.jpg": "2018-03-09",
        "063.jpg": "2018-02-26",
        "074.jpg": "2018-03-20",
        "080.jpg": "2017-09-21",
        "090.jpg": "2017-03-13",
        "097.jpg": "2018-01-12",
    }

    for filename, exp_date in expected.items():
        assert filename in date_lookup, f"Missing row for {filename}"
        actual_date = date_lookup[filename]
        assert actual_date == exp_date, (
            f"Date mismatch for {filename}: actual={actual_date!r}, expected={exp_date!r}"
        )
