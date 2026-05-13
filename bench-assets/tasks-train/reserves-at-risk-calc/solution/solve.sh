#!/bin/bash
#
# Reserves at Risk (RaR) — TRAIN VARIANT solver.
# Different code organization than val: helper class, distinct variable names,
# operates on pre-loaded gold price column (no live IMF download).

set -euo pipefail

mkdir -p /root/output

python3 << 'PYEOF'
import math
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

CONFIDENCE_Z = 1.65   # 95% one-sided shock
DATA_YEAR    = 2026   # latest reporting year in this variant
WINDOW_LABEL = "Q1"   # Jan-Mar 2026 averaging window for Volume->Value conversion
SRC_BOOK     = '/root/data/test-rar.xlsx'
DEST_BOOK    = '/root/output/rar_result.xlsx'


class RaRWorkbook:
    """Lightweight wrapper around the four IMF-style sheets + Answer sheet."""

    def __init__(self, path):
        self.book = load_workbook(path)
        self.gold  = self.book['Gold price']
        self.ans   = self.book['Answer']
        self.tot   = self.book['Total Reserves']
        self.val   = self.book['Value']
        self.vol   = self.book['Volume']

    # ---- Gold-price formulas ----
    def install_gold_formulas(self):
        """Populate columns C/D/E of 'Gold price' with LN return + STDEV.S formulas."""
        n_rows = self.gold.max_row
        # Row 2 is the first data point; log returns start row 3.
        for row in range(3, n_rows + 1):
            self.gold[f'C{row}'] = f'=LN(B{row}/B{row-1})*100'
        # 3-month rolling window: needs 3 log returns -> earliest row = 5
        for row in range(5, n_rows + 1):
            self.gold[f'D{row}'] = f'=_xlfn.STDEV.S(C{row-2}:C{row})'
        # 12-month rolling window: needs 12 log returns -> earliest row = 14
        for row in range(14, n_rows + 1):
            self.gold[f'E{row}'] = f'=_xlfn.STDEV.S(C{row-11}:C{row})'
        return n_rows  # last row, used for Answer references

    # ---- Sheet helpers ----
    @staticmethod
    def _country_from_header(header):
        return None if not header else header.split(':')[0].strip()

    def _year_row(self, sheet, year):
        for r in range(10, sheet.max_row + 1):
            label = sheet.cell(row=r, column=1).value
            if label and str(year) in str(label):
                return r
        return None

    def collect_year(self, sheet, year):
        """Return ordered list of (country, value, col_letter, row) for a target year."""
        yr_row = self._year_row(sheet, year)
        if yr_row is None:
            return []
        results = []
        for col in range(3, sheet.max_column + 1):
            country = self._country_from_header(sheet.cell(row=1, column=col).value)
            if not country:
                continue
            cell_val = sheet.cell(row=yr_row, column=col).value
            if cell_val is None or cell_val == '' or isinstance(cell_val, str):
                continue
            results.append((country, cell_val, get_column_letter(col), yr_row))
        return results


# === Main ===
print('[1/4] Opening source workbook...')
wb = RaRWorkbook(SRC_BOOK)

print('[2/4] Installing Gold price formulas...')
last_row = wb.install_gold_formulas()
print(f'      last gold row = {last_row}')

# --- STEP 1: Answer C3..C6 ---
print('[3/4] Filling Answer STEP 1 (volatility)...')
wb.ans['C3'] = CONFIDENCE_Z
wb.ans['C4'] = f"='Gold price'!D{last_row}"
wb.ans['C5'] = f"='Gold price'!D{last_row}*SQRT(12)"
wb.ans['C6'] = f"='Gold price'!E{last_row}"

# --- STEP 2: Country exposure table ---
print('[3/4] Filling Answer STEP 2...')
value_records  = wb.collect_year(wb.val, DATA_YEAR)
volume_records = wb.collect_year(wb.vol, DATA_YEAR)

# Q1-2026 averaging window for Volume->Value conversion
# Last 3 gold-price rows correspond to 2026M1, 2026M2, 2026M3
window_start = last_row - 2
window_end   = last_row
avg_price_expr = f"AVERAGE('Gold price'!B{window_start}:B{window_end})"

# Build ordered country list per val pattern:
# (a) all Value-sheet countries (in sheet column order)
step2_entries = []  # list of (country, gold_reserve_expression, raw_numeric_for_step3_reuse)
seen_country = set()
for country, raw_val, col_letter, yr_row in value_records:
    expr = f"='Value'!{col_letter}{yr_row}"
    step2_entries.append((country, expr))
    seen_country.add(country)

# (b) Volume-only countries: convert via avg gold price (Mil.Troy.Oz * USD/oz -> Mil.USD)
for country, raw_val, col_letter, yr_row in volume_records:
    if country in seen_country:
        continue  # already covered by Value sheet
    expr = f"='Volume'!{col_letter}{yr_row}*{avg_price_expr}"
    step2_entries.append((country, expr))
    seen_country.add(country)

# Write to Answer rows 11/12/13
answer_cols = [get_column_letter(3 + i) for i in range(len(step2_entries))]
for col_letter, (country, gold_expr) in zip(answer_cols, step2_entries):
    wb.ans[f'{col_letter}11'] = country
    wb.ans[f'{col_letter}12'] = gold_expr
    # Gold valuation exposure = gold_reserve * (z / 100) * vol_3m
    wb.ans[f'{col_letter}13'] = f'={col_letter}12*$C$3/100*$C$4'

# --- STEP 3: RaR as % of total reserves (only countries with 2026 Total Reserves) ---
print('[3/4] Filling Answer STEP 3...')
total_records = wb.collect_year(wb.tot, DATA_YEAR)
total_lookup  = {country: (col_letter, yr_row) for country, _, col_letter, yr_row in total_records}

step3_pairs = []
for country, gold_expr in step2_entries:
    if country in total_lookup:
        step3_pairs.append((country, gold_expr, total_lookup[country]))

s3_cols = [get_column_letter(3 + i) for i in range(len(step3_pairs))]
for col_letter, (country, gold_expr, (tr_col, tr_row)) in zip(s3_cols, step3_pairs):
    wb.ans[f'{col_letter}20'] = country
    wb.ans[f'{col_letter}21'] = gold_expr
    wb.ans[f'{col_letter}22'] = f'={col_letter}21*$C$3/100*$C$4'
    wb.ans[f'{col_letter}23'] = f"='Total Reserves'!{tr_col}{tr_row}"
    wb.ans[f'{col_letter}24'] = f'={col_letter}22/{col_letter}23*100'

print('[4/4] Saving result workbook...')
wb.book.save(DEST_BOOK)
print(f'      saved -> {DEST_BOOK}')
PYEOF

# Recalculate formulas via LibreOffice headless so the xlsx ships with cached values.
# Fall back to the xlsx skill's recalc helper when present (Harbor Anthropic-skills env).
if command -v soffice &> /dev/null; then
    echo "Recalculating formulas with LibreOffice headless..."
    cd /root/output
    if [ -f /root/.claude/skills/xlsx/recalc.py ]; then
        python3 /root/.claude/skills/xlsx/recalc.py rar_result.xlsx 60 || true
    else
        # Headless conversion forces formula evaluation and rewrites cached values.
        soffice --headless --calc --convert-to xlsx --outdir /tmp/_recalc rar_result.xlsx >/dev/null 2>&1 || true
        if [ -f /tmp/_recalc/rar_result.xlsx ]; then
            mv /tmp/_recalc/rar_result.xlsx rar_result.xlsx
        fi
    fi
fi

# Convert to CSV so the verifier can read evaluated values
if command -v ssconvert &> /dev/null; then
    cd /root/output
    ssconvert --export-type=Gnumeric_stf:stf_csv rar_result.xlsx sheet.csv 2>/dev/null || true
fi

echo "Solution completed."
