#!/bin/bash
set -e

EXCEL_FILE="/root/savings_rate.xlsx"

cat > /tmp/solve_savings.py << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
"""
Oracle solution for population-weighted savings rate calculation.

Populates the Task sheet with computed values for:
- Step 1: Data lookup from the Data sheet (GNI, consumption, population by country/year)
- Step 2: Gross savings rate + statistics (MIN/MAX/MEDIAN/AVERAGE/PERCENTILE/STDEV)
- Step 3: Population-weighted mean using SUMPRODUCT logic
"""

import math
from openpyxl import load_workbook

EXCEL_FILE = "/root/savings_rate.xlsx"

def main():
    wb = load_workbook(EXCEL_FILE)

    task_sheet = None
    for sheet_name in wb.sheetnames:
        if sheet_name == 'Task' or 'Task' in sheet_name:
            task_sheet = wb[sheet_name]
            break
    if task_sheet is None:
        task_sheet = wb.active
    ws = task_sheet

    data_ws = None
    for sheet_name in wb.sheetnames:
        if sheet_name == 'Data':
            data_ws = wb[sheet_name]
            break
    if data_ws is None:
        print("ERROR: Data sheet not found!")
        return

    columns = ['F', 'G', 'H', 'I']
    years = [2020, 2021, 2022, 2023]
    year_row = 8

    for col_idx, col in enumerate(columns):
        ws[f'{col}{year_row}'] = years[col_idx]

    # Map years to their column indices in the Data sheet (row 3 has headers, data cols E-H = 5-8)
    year_to_col = {}
    for col_idx in range(1, 20):
        cell_val = data_ws.cell(row=3, column=col_idx).value
        if cell_val is not None:
            try:
                yr = int(cell_val)
                if yr in years:
                    year_to_col[yr] = col_idx
            except (ValueError, TypeError):
                pass

    # Map (series_code, country) to row in Data sheet (rows 5-19)
    def build_lookup():
        lookup = {}
        for row in range(5, 25):
            country = data_ws.cell(row=row, column=1).value
            series_code = data_ws.cell(row=row, column=2).value
            if country and series_code:
                lookup[(series_code, country)] = row
        return lookup

    data_lookup = build_lookup()

    def lookup_value(series_code, country, year):
        key = (series_code, country)
        if key not in data_lookup:
            return 0
        if year not in year_to_col:
            return 0
        row = data_lookup[key]
        col = year_to_col[year]
        val = data_ws.cell(row=row, column=col).value
        return val if val is not None else 0

    gni_rows = list(range(11, 16))
    cons_rows = list(range(18, 23))
    pop_rows = list(range(25, 30))

    # Step 1: Populate GNI, consumption, population values from Data sheet lookups
    for row in gni_rows:
        series_code = ws.cell(row=row, column=3).value  # Column C has series code
        country = ws.cell(row=row, column=2).value  # Column B has country
        for col_idx, col in enumerate(columns):
            year = years[col_idx]
            value = lookup_value(series_code, country, year)
            ws[f'{col}{row}'] = value

    for row in cons_rows:
        series_code = ws.cell(row=row, column=3).value
        country = ws.cell(row=row, column=2).value
        for col_idx, col in enumerate(columns):
            year = years[col_idx]
            value = lookup_value(series_code, country, year)
            ws[f'{col}{row}'] = value

    for row in pop_rows:
        series_code = ws.cell(row=row, column=3).value
        country = ws.cell(row=row, column=2).value
        for col_idx, col in enumerate(columns):
            year = years[col_idx]
            value = lookup_value(series_code, country, year)
            ws[f'{col}{row}'] = value

    # Step 2: Calculate savings rate = (GNI - Consumption) / GNI * 100
    savings_rows = list(range(33, 38))
    for row_idx, row in enumerate(savings_rows):
        gni_row = 11 + row_idx
        cons_row = 18 + row_idx

        for col_idx, col in enumerate(columns):
            gni_val = ws[f'{col}{gni_row}'].value or 0
            cons_val = ws[f'{col}{cons_row}'].value or 0

            if gni_val != 0:
                savings_pct = (gni_val - cons_val) / gni_val * 100
            else:
                savings_pct = 0
            ws[f'{col}{row}'] = round(savings_pct, 1)

    # Step 2 continued: Compute statistics
    for col_idx, col in enumerate(columns):
        values = [ws[f'{col}{r}'].value or 0 for r in range(33, 38)]
        n = len(values)
        ws[f'{col}40'] = min(values)  # MIN
        ws[f'{col}41'] = max(values)  # MAX
        sorted_vals = sorted(values)
        ws[f'{col}42'] = sorted_vals[2]  # MEDIAN (5 values -> middle)
        ws[f'{col}43'] = round(sum(values) / n, 1)  # AVERAGE
        # PERCENTILE.INC(arr, 0.25): index = 0.25*(n-1) = 1.0 for n=5
        ws[f'{col}44'] = sorted_vals[1]  # 25th percentile
        # PERCENTILE.INC(arr, 0.75): index = 0.75*(n-1) = 3.0 for n=5
        ws[f'{col}45'] = sorted_vals[3]  # 75th percentile
        # STDEV (sample standard deviation)
        mean_v = sum(values) / n
        variance = sum((v - mean_v) ** 2 for v in values) / (n - 1)
        ws[f'{col}46'] = round(math.sqrt(variance), 1)  # STDEV

    # Step 3: Population-weighted mean = SUMPRODUCT(savings_rate, population) / SUM(population)
    for col_idx, col in enumerate(columns):
        savings_pct = [ws[f'{col}{r}'].value or 0 for r in range(33, 38)]
        pop_values = [ws[f'{col}{r}'].value or 0 for r in range(25, 30)]

        sumproduct = sum(pct * pop for pct, pop in zip(savings_pct, pop_values))
        sum_pop = sum(pop_values)
        weighted_mean = sumproduct / sum_pop if sum_pop != 0 else 0
        ws[f'{col}49'] = round(weighted_mean, 1)

    wb.save(EXCEL_FILE)
    wb.close()
    print("Successfully computed all values.")

if __name__ == '__main__':
    main()
PYTHON_SCRIPT

python3 /tmp/solve_savings.py
echo "Solution complete."
