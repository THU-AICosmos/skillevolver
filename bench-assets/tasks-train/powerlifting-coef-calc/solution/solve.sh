#!/bin/bash

set -e
# Use this file to solve the task.

WORKSPACE=/root/workspace
SRC_FILE="/root/data/weightlifting_results.xlsx"
DST_FILE="/root/data/weightlifting_output.xlsx"
mkdir -p ${WORKSPACE}

uv init --python 3.12
uv add typer==0.21.1
uv add polars==1.37.1
uv add xlsxwriter==3.2.9
uv add fastexcel==0.18.0


cat > $WORKSPACE/sinclair_calc.py << 'PYTHON_SCRIPT'
"""
Olympic Weightlifting Sinclair coefficient calculator.

Writes Excel formulas to the "Sinclair" sheet that reference data from the "Results" sheet.
Computes TotalKg and Sinclair coefficient using Excel formulas.

Based on IWF Sinclair Coefficients:
https://iwf.sport/weightlifting_/sinclair-coefficient/
"""

import polars as pl
import xlsxwriter


def build_sinclair_formula(gender_ref: str, bw_ref: str, total_ref: str) -> str:
    """
    Generate the Excel formula for the Sinclair coefficient.

    Formula:
      - If bodyweight >= threshold: Sinclair = Total
      - If bodyweight < threshold: Sinclair = Total * 10^(A * LOG10(bw/threshold)^2)

    For males: A=0.751945030, threshold=200
    For females: A=0.783497476, threshold=175
    """
    # Male parameters
    m_coeff = 0.751945030
    m_thresh = 200.0
    # Female parameters
    f_coeff = 0.783497476
    f_thresh = 175.0

    # Male sinclair: if bw >= 200, just total; else total * 10^(A*(LOG10(bw/200))^2)
    male_expr = (
        f"IF({bw_ref}>={m_thresh},"
        f"{total_ref},"
        f"{total_ref}*POWER(10,{m_coeff}*POWER(LOG10({bw_ref}/{m_thresh}),2)))"
    )

    # Female sinclair: if bw >= 175, just total; else total * 10^(A*(LOG10(bw/175))^2)
    female_expr = (
        f"IF({bw_ref}>={f_thresh},"
        f"{total_ref},"
        f"{total_ref}*POWER(10,{f_coeff}*POWER(LOG10({bw_ref}/{f_thresh}),2)))"
    )

    # Choose based on gender
    formula = f'=ROUND(IF({gender_ref}="M",{male_expr},{female_expr}),3)'
    return formula


def run(
    src_path: str = "/root/data/weightlifting_results.xlsx",
    dst_path: str = "/root/data/weightlifting_output.xlsx",
):
    """
    Read the weightlifting Excel file and write formulas to the Sinclair sheet.

    The Sinclair sheet will contain:
    - Column A: Athlete (from Results!A)
    - Column B: Gender (from Results!B)
    - Column C: BodyweightKg (from Results!E)
    - Column D: BestSnatchKg (from Results!G)
    - Column E: BestCleanJerkKg (from Results!H)
    - Column F: TotalKg (computed: D+E)
    - Column G: Sinclair (computed using formula)
    """
    # Load data to determine row count and column mapping
    df = pl.read_excel(src_path, sheet_name="Results")
    n_athletes = df.height
    print(f"Processing {n_athletes} athletes from {src_path}")

    with xlsxwriter.Workbook(dst_path) as workbook:
        # Recreate the Results sheet with original data
        results_ws = workbook.add_worksheet("Results")

        # Write headers
        for ci, col in enumerate(df.columns):
            results_ws.write(0, ci, col)

        # Write data rows
        for ri, record in enumerate(df.iter_rows()):
            for ci, val in enumerate(record):
                results_ws.write(ri + 1, ci, val)

        # Create the Sinclair sheet with formulas
        sinclair_ws = workbook.add_worksheet("Sinclair")

        col_labels = [
            "Athlete",
            "Gender",
            "BodyweightKg",
            "BestSnatchKg",
            "BestCleanJerkKg",
            "TotalKg",
            "Sinclair",
        ]
        for ci, label in enumerate(col_labels):
            sinclair_ws.write(0, ci, label)

        # Map: Results columns A=Athlete, B=Gender, E=BodyweightKg, G=BestSnatchKg, H=BestCleanJerkKg
        for excel_row in range(2, n_athletes + 2):
            row_idx = excel_row - 1
            # Column A: Athlete from Results!A
            sinclair_ws.write_formula(row_idx, 0, f"=Results!A{excel_row}")
            # Column B: Gender from Results!B
            sinclair_ws.write_formula(row_idx, 1, f"=Results!B{excel_row}")
            # Column C: BodyweightKg from Results!E
            sinclair_ws.write_formula(row_idx, 2, f"=Results!E{excel_row}")
            # Column D: BestSnatchKg from Results!G
            sinclair_ws.write_formula(row_idx, 3, f"=Results!G{excel_row}")
            # Column E: BestCleanJerkKg from Results!H
            sinclair_ws.write_formula(row_idx, 4, f"=Results!H{excel_row}")
            # Column F: TotalKg = D + E (snatch + clean&jerk)
            sinclair_ws.write_formula(row_idx, 5, f"=D{excel_row}+E{excel_row}")
            # Column G: Sinclair formula
            sinclair_formula = build_sinclair_formula(
                f"B{excel_row}", f"C{excel_row}", f"F{excel_row}"
            )
            sinclair_ws.write_formula(row_idx, 6, sinclair_formula)

    print(f"Wrote formulas to {dst_path}")


if __name__ == "__main__":
    import typer
    typer.run(run)
PYTHON_SCRIPT

uv run $WORKSPACE/sinclair_calc.py --src-path $SRC_FILE --dst-path $DST_FILE
mv $DST_FILE $SRC_FILE
echo "Sinclair calculation complete."
