#!/bin/bash
set -e

EXCEL_FILE="/root/metabolite_abundance.xlsx"

cat > /tmp/solve_metabolite.py << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
"""
Oracle solution for Metabolite Abundance Analysis.

Uses openpyxl to:
1. Lookup abundance values from Data sheet (like VLOOKUP/INDEX-MATCH)
2. Calculate statistics (mean, std)
3. Calculate fold changes
"""

from openpyxl import load_workbook
import statistics
import math

EXCEL_FILE = "/root/metabolite_abundance.xlsx"

def lookup_value(data_ws, metabolite_id, sample_name):
    """
    Implement INDEX-MATCH logic: find metabolite_id in column A,
    then find sample_name in row 1, return intersection value.
    """
    # Find metabolite row
    met_row = None
    for row in range(2, data_ws.max_row + 1):
        if data_ws.cell(row=row, column=1).value == metabolite_id:
            met_row = row
            break

    if met_row is None:
        return None

    # Find sample column
    sample_col = None
    for col in range(1, data_ws.max_column + 1):
        if data_ws.cell(row=1, column=col).value == sample_name:
            sample_col = col
            break

    if sample_col is None:
        return None

    return data_ws.cell(row=met_row, column=sample_col).value

def main():
    print("Loading workbook...")
    wb = load_workbook(EXCEL_FILE)

    task_ws = wb['Task']
    data_ws = wb['Data']

    print("Step 1: Lookup abundance values...")
    # Get target metabolites and samples from Task sheet
    target_metabolites = []
    for row in range(8, 16):  # Rows 8-15
        met_id = task_ws.cell(row=row, column=1).value
        if met_id:
            target_metabolites.append(met_id)

    target_samples = []
    for col in range(3, 15):  # Columns C-N (3-14)
        sample_name = task_ws.cell(row=7, column=col).value
        if sample_name:
            target_samples.append(sample_name)

    # Fill abundance values using lookup
    for row_idx, met_id in enumerate(target_metabolites, 8):
        for col_idx, sample_name in enumerate(target_samples, 3):
            value = lookup_value(data_ws, met_id, sample_name)
            task_ws.cell(row=row_idx, column=col_idx, value=value)

    print(f"Filled {len(target_metabolites)} x {len(target_samples)} cells")

    print("Step 2: Calculate statistics...")
    # Read sample groups from row 6 of Task sheet
    healthy_samples = []
    diseased_samples = []

    for col in range(1, data_ws.max_column + 1):
        sample_name = data_ws.cell(row=1, column=col).value
        if sample_name is None:
            continue

        # Find this sample in Task sheet row 7 and check its group in row 6
        for task_col in range(3, 15):  # Columns C-N
            task_sample = task_ws.cell(row=7, column=task_col).value
            if task_sample == sample_name:
                group = task_ws.cell(row=6, column=task_col).value
                if group == 'Healthy':
                    healthy_samples.append(sample_name)
                elif group == 'Diseased':
                    diseased_samples.append(sample_name)
                break

    # For each target metabolite, calculate statistics
    for col_idx, met_id in enumerate(target_metabolites, 2):  # Column B onwards
        # Get all values for this metabolite from Data sheet
        met_row = None
        for row in range(2, data_ws.max_row + 1):
            if data_ws.cell(row=row, column=1).value == met_id:
                met_row = row
                break

        if met_row is None:
            continue

        # Extract healthy and diseased values
        healthy_values = []
        diseased_values = []

        for col in range(1, data_ws.max_column + 1):
            sample_name = data_ws.cell(row=1, column=col).value
            value = data_ws.cell(row=met_row, column=col).value

            if sample_name in healthy_samples and value is not None:
                try:
                    healthy_values.append(float(value))
                except:
                    pass
            elif sample_name in diseased_samples and value is not None:
                try:
                    diseased_values.append(float(value))
                except:
                    pass

        # Calculate statistics
        if healthy_values:
            h_mean = statistics.mean(healthy_values)
            h_std = statistics.stdev(healthy_values) if len(healthy_values) > 1 else 0
        else:
            h_mean = h_std = 0

        if diseased_values:
            d_mean = statistics.mean(diseased_values)
            d_std = statistics.stdev(diseased_values) if len(diseased_values) > 1 else 0
        else:
            d_mean = d_std = 0

        # Write to Task sheet (rows 19-22)
        task_ws.cell(row=19, column=col_idx, value=round(h_mean, 3))
        task_ws.cell(row=20, column=col_idx, value=round(h_std, 3))
        task_ws.cell(row=21, column=col_idx, value=round(d_mean, 3))
        task_ws.cell(row=22, column=col_idx, value=round(d_std, 3))

    print("Statistics calculated")

    print("Step 3: Calculate fold changes...")
    for row_idx in range(27, 35):  # Rows 27-34
        # Get metabolite ID and common name
        met_id = task_ws.cell(row=8 + (row_idx - 27), column=1).value
        common_name = task_ws.cell(row=8 + (row_idx - 27), column=2).value

        task_ws.cell(row=row_idx, column=1, value=met_id)
        task_ws.cell(row=row_idx, column=2, value=common_name)

        # Get healthy and diseased means
        col_idx_for_met = 2 + (row_idx - 27)  # Column B + offset
        h_mean = task_ws.cell(row=19, column=col_idx_for_met).value or 0
        d_mean = task_ws.cell(row=21, column=col_idx_for_met).value or 0

        # For log2-transformed data
        log2fc = d_mean - h_mean
        fc = 2 ** log2fc

        task_ws.cell(row=row_idx, column=3, value=round(log2fc, 3))
        task_ws.cell(row=row_idx, column=4, value=round(fc, 3))

    print("Fold changes calculated")

    print("Saving workbook...")
    wb.save(EXCEL_FILE)
    wb.close()

    print("Task completed successfully!")

if __name__ == '__main__':
    main()
PYTHON_SCRIPT

python3 /tmp/solve_metabolite.py
echo "Solution complete."
