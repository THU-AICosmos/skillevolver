#!/bin/bash
set -e

cat > /tmp/solve_education_report.py << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
"""Oracle solution for Canadian Education Pivot Table Analysis task."""
import pandas as pd
import pdfplumber
from openpyxl import Workbook
from openpyxl.pivot.table import TableDefinition, Location, PivotField, DataField, RowColField
from openpyxl.pivot.cache import CacheDefinition, CacheField, CacheSource, WorksheetSource, SharedItems

# Extract enrollment data from PDF
def extract_enrollment_from_pdf(pdf_path):
    """Extract enrollment data from all pages of the PDF."""
    all_data = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if row and len(row) >= 4:
                        # Skip header rows
                        if row[0] and str(row[0]).strip().isdigit():
                            all_data.append({
                                'SCHOOL_ID': int(row[0]),
                                'SCHOOL_NAME': str(row[1]).strip() if row[1] else '',
                                'PROVINCE': str(row[2]).strip() if row[2] else '',
                                'ENROLLMENT_2024': int(str(row[3]).replace(',', '')) if row[3] else 0
                            })
    return pd.DataFrame(all_data)

# Load data
enroll_df = extract_enrollment_from_pdf("/root/enrollment.pdf")
perf_df = pd.read_excel("/root/performance.xlsx")

# Convert performance columns to numeric
for col in ['TEACHERS', 'AVG_SCORE', 'FUNDING']:
    if col in perf_df.columns:
        perf_df[col] = pd.to_numeric(perf_df[col].astype(str).str.replace(',', ''), errors='coerce')

# Join on SCHOOL_ID
df = enroll_df.merge(perf_df, on='SCHOOL_ID', how='inner', suffixes=('', '_perf'))

# Use SCHOOL_NAME from enrollment data, drop duplicate from performance
if 'SCHOOL_NAME_perf' in df.columns:
    df = df.drop(columns=['SCHOOL_NAME_perf'])

# Calculate Tier based on FUNDING quartiles
quartiles = df['FUNDING'].quantile([0.25, 0.5, 0.75])
def get_tier(val):
    if pd.isna(val):
        return 'T1'
    if val <= quartiles[0.25]:
        return 'T1'
    elif val <= quartiles[0.5]:
        return 'T2'
    elif val <= quartiles[0.75]:
        return 'T3'
    else:
        return 'T4'

df['Tier'] = df['FUNDING'].apply(get_tier)

# Calculate Budget = TEACHERS × FUNDING
df['Budget'] = df['TEACHERS'] * df['FUNDING']

# Create workbook with source data
wb = Workbook()
ws = wb.active
ws.title = "SourceData"
HEADERS = ["SCHOOL_ID", "SCHOOL_NAME", "PROVINCE", "ENROLLMENT_2024", "TEACHERS", "AVG_SCORE", "FUNDING", "Tier", "Budget"]
ws.append(HEADERS)
for row in df[HEADERS].itertuples(index=False):
    ws.append(list(row))

def make_cache(num_rows):
    return CacheDefinition(
        cacheSource=CacheSource(type="worksheet", worksheetSource=WorksheetSource(ref=f"A1:I{num_rows}", sheet="SourceData")),
        cacheFields=[CacheField(name=h, sharedItems=SharedItems()) for h in HEADERS],
    )

def add_pivot(wb, sheet_name, name, row_idx, data_idx, subtotal, col_idx=None):
    """Create a pivot table with row field, optional column field, and data field."""
    pivot_ws = wb.create_sheet(sheet_name)
    loc_ref = "A3:F15" if col_idx else "A3:B15"
    pivot = TableDefinition(name=name, cacheId=0, dataCaption=subtotal.title(),
                            location=Location(ref=loc_ref, firstHeaderRow=1, firstDataRow=1 if not col_idx else 2, firstDataCol=1))
    for i in range(len(HEADERS)):
        axis = "axisRow" if i == row_idx else ("axisCol" if i == col_idx else None)
        pivot.pivotFields.append(PivotField(axis=axis, dataField=(i == data_idx), showAll=False))
    pivot.rowFields.append(RowColField(x=row_idx))
    if col_idx:
        pivot.colFields.append(RowColField(x=col_idx))
    pivot.dataFields.append(DataField(name=name, fld=data_idx, subtotal=subtotal))
    pivot.cache = make_cache(len(df) + 1)
    pivot_ws._pivots.append(pivot)

# HEADERS = ["SCHOOL_ID", "SCHOOL_NAME", "PROVINCE", "ENROLLMENT_2024", "TEACHERS", "AVG_SCORE", "FUNDING", "Tier", "Budget"]
#              0              1              2              3                4           5            6          7       8

add_pivot(wb, "Enrollment by Province", "Total Enrollment", row_idx=2, data_idx=3, subtotal="sum")
add_pivot(wb, "Teachers by Province", "Total Teachers", row_idx=2, data_idx=4, subtotal="sum")
add_pivot(wb, "Schools by Province", "School Count", row_idx=2, data_idx=0, subtotal="count")
add_pivot(wb, "Province Funding Tier", "Teachers", row_idx=2, data_idx=4, subtotal="sum", col_idx=7)

wb.save("/root/education_report.xlsx")
print("Done!")
PYTHON_SCRIPT

python3 /tmp/solve_education_report.py
