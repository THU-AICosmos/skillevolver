#!/bin/bash
set -e

# Water Quality Unit Harmonization Solution
# Cleans format issues and converts units to US EPA standard

WATER_INPUT="/root/environment/data/water_quality_data.csv"
WATER_OUTPUT="/root/water_quality_harmonized.csv"

cat > /tmp/wq_harmonize.py << 'PYEOF'
#!/usr/bin/env python3
"""
Water quality data harmonization pipeline.

Steps:
1. Drop rows with any missing values
2. Parse formats (scientific notation, European comma decimals)
3. Detect out-of-range values and apply unit conversion
4. Format all values to 2 decimal places
"""

import pandas as pd
import numpy as np

SRC = "/root/environment/data/water_quality_data.csv"
DST = "/root/water_quality_harmonized.csv"

# Expected ranges in target units (US EPA standard)
VALID_RANGES = {
    'pH': (6.0, 9.0),
    'Turbidity_NTU': (0.1, 500.0),
    'Conductivity_uS_cm': (10.0, 5000.0),
    'Temperature_C': (0.5, 40.0),
    'Dissolved_Oxygen_Pct': (10.0, 200.0),
    'UV254_Absorbance': (0.0, 2.0),
    'ORP_mV': (-500.0, 800.0),
    'Color_PCU': (1.0, 500.0),
    'Odor_TON': (1.0, 200.0),
    'Total_Coliform_CFU': (0.0, 50000.0),
    'E_Coli_CFU': (0.0, 10000.0),
    'Fecal_Coliform_CFU': (0.0, 20000.0),
    'BOD5_mg_L': (0.5, 300.0),
    'COD_mg_L': (1.0, 1000.0),
    'Chlorophyll_a_ug_L': (0.1, 500.0),
    'Dissolved_Oxygen_mg_L': (1.0, 20.0),
    'Nitrate_N_mg_L': (0.01, 50.0),
    'Nitrite_N_mg_L': (0.0, 5.0),
    'Ammonia_N_mg_L': (0.01, 30.0),
    'Total_Kjeldahl_N_mg_L': (0.1, 50.0),
    'Total_Phosphorus_mg_L': (0.01, 20.0),
    'Orthophosphate_mg_L': (0.005, 10.0),
    'Sulfate_mg_L': (1.0, 1000.0),
    'Chloride_mg_L': (1.0, 1000.0),
    'Fluoride_mg_L': (0.01, 10.0),
    'Calcium_mg_L': (1.0, 500.0),
    'Magnesium_mg_L': (0.5, 200.0),
    'Sodium_mg_L': (1.0, 1000.0),
    'Potassium_mg_L': (0.5, 50.0),
    'Hardness_CaCO3_mg_L': (5.0, 1500.0),
    'Alkalinity_CaCO3_mg_L': (5.0, 500.0),
    'Lead_ug_L': (0.1, 500.0),
    'Mercury_ug_L': (0.01, 50.0),
    'Cadmium_ug_L': (0.05, 100.0),
    'Arsenic_ug_L': (0.5, 500.0),
    'Chromium_ug_L': (0.5, 500.0),
    'Copper_ug_L': (0.5, 5000.0),
    'Zinc_ug_L': (1.0, 10000.0),
    'Nickel_ug_L': (0.5, 1000.0),
    'Selenium_ug_L': (0.1, 200.0),
    'Manganese_ug_L': (1.0, 5000.0),
    'Iron_ug_L': (5.0, 50000.0),
    'Barium_ug_L': (1.0, 5000.0),
    'Total_THM_ug_L': (0.5, 500.0),
    'Benzene_ug_L': (0.1, 100.0),
    'Toluene_ug_L': (0.1, 2000.0),
    'TDS_mg_L': (10.0, 10000.0),
    'TSS_mg_L': (1.0, 5000.0),
    'Total_Nitrogen_mg_L': (0.1, 100.0),
    'Silica_mg_L': (0.5, 100.0),
}

# Conversion factors: value_in_alt_unit * factor = value_in_target_unit
# These are the RECIPROCAL of the dirty factors used during data generation
UNIT_CORRECTIONS = {
    # Dissolved oxygen: mmol/L -> mg/L (×32)
    'Dissolved_Oxygen_mg_L': [1.0 / 0.03125],

    # Nitrogen species: mmol/L -> mg/L as N (×14.01)
    'Nitrate_N_mg_L': [1.0 / 0.0714],
    'Nitrite_N_mg_L': [1.0 / 0.0714],
    'Ammonia_N_mg_L': [1.0 / 0.0714],
    'Total_Kjeldahl_N_mg_L': [1.0 / 0.0714],
    'Total_Nitrogen_mg_L': [1.0 / 0.0714],

    # Phosphorus species: mmol/L -> mg/L (×30.97)
    'Total_Phosphorus_mg_L': [1.0 / 0.0323],
    'Orthophosphate_mg_L': [1.0 / 0.0323],

    # Major ions: mmol/L -> mg/L
    'Sulfate_mg_L': [1.0 / 0.01042],
    'Chloride_mg_L': [1.0 / 0.02821],
    'Fluoride_mg_L': [1.0 / 0.05263],
    'Calcium_mg_L': [1.0 / 0.02495],
    'Magnesium_mg_L': [1.0 / 0.04114],
    'Sodium_mg_L': [1.0 / 0.04348],
    'Potassium_mg_L': [1.0 / 0.02558],

    # Hardness/Alkalinity: mmol/L -> mg/L as CaCO3
    'Hardness_CaCO3_mg_L': [1.0 / 0.01],
    'Alkalinity_CaCO3_mg_L': [1.0 / 0.01],

    # Heavy metals: mg/L -> µg/L (×1000)
    'Lead_ug_L': [1.0 / 0.001],
    'Mercury_ug_L': [1.0 / 0.001],
    'Cadmium_ug_L': [1.0 / 0.001],
    'Arsenic_ug_L': [1.0 / 0.001],
    'Chromium_ug_L': [1.0 / 0.001],
    'Copper_ug_L': [1.0 / 0.001],
    'Zinc_ug_L': [1.0 / 0.001],
    'Nickel_ug_L': [1.0 / 0.001],
    'Selenium_ug_L': [1.0 / 0.001],
    'Manganese_ug_L': [1.0 / 0.001],
    'Iron_ug_L': [1.0 / 0.001],
    'Barium_ug_L': [1.0 / 0.001],

    # Organic compounds: mg/L -> µg/L (×1000)
    'Total_THM_ug_L': [1.0 / 0.001],
    'Benzene_ug_L': [1.0 / 0.001],
    'Toluene_ug_L': [1.0 / 0.001],

    # Solids: g/L -> mg/L (×1000)
    'TDS_mg_L': [1.0 / 0.001],
    'TSS_mg_L': [1.0 / 0.001],

    # Silica: mmol/L -> mg/L (×60.08)
    'Silica_mg_L': [1.0 / 0.01664],
}


def text_to_float(raw_val):
    """Parse a potentially messy string to float, handling sci notation and European commas."""
    if pd.isna(raw_val):
        return np.nan
    txt = str(raw_val).strip()
    if txt == '' or txt.lower() in ('nan', 'none'):
        return np.nan
    # Scientific notation first
    if 'e' in txt.lower():
        try:
            return float(txt)
        except ValueError:
            pass
    # European comma -> dot
    if ',' in txt:
        txt = txt.replace(',', '.')
    try:
        return float(txt)
    except ValueError:
        return np.nan


def fix_units(val, col_name):
    """If value is outside expected range, try applying conversion factors."""
    if pd.isna(val) or col_name not in VALID_RANGES:
        return val
    lo, hi = VALID_RANGES[col_name]
    if lo <= val <= hi:
        return val
    if col_name not in UNIT_CORRECTIONS:
        return val
    spread = hi - lo
    margin = spread * 0.05
    for mult in UNIT_CORRECTIONS[col_name]:
        candidate = val * mult
        if (lo - margin) <= candidate <= (hi + margin):
            return max(lo, min(hi, candidate))
    return val


def run_pipeline():
    print(f"Reading {SRC} ...")
    raw = pd.read_csv(SRC, dtype=str)
    measure_cols = [c for c in raw.columns if c != 'station_id']
    print(f"  {len(raw)} rows, {len(measure_cols)} measurement columns")

    # 1 - drop incomplete rows
    def has_gap(row):
        for c in measure_cols:
            v = row[c]
            if pd.isna(v) or str(v).strip() in ('', 'NaN', 'None', 'nan', 'none'):
                return True
        return False

    mask_complete = ~raw.apply(has_gap, axis=1)
    n_dropped = (~mask_complete).sum()
    raw = raw[mask_complete].reset_index(drop=True)
    print(f"  Dropped {n_dropped} incomplete rows -> {len(raw)} remaining")

    # 2 - parse numeric formats
    for c in measure_cols:
        raw[c] = raw[c].apply(text_to_float)

    # 3 - unit corrections
    n_fixes = 0
    for c in measure_cols:
        before = raw[c].copy()
        raw[c] = raw[c].apply(lambda v: fix_units(v, c))
        n_fixes += (before != raw[c]).sum()
    print(f"  Applied {n_fixes} unit corrections")

    # 4 - format to 2 decimal places
    for c in measure_cols:
        raw[c] = raw[c].apply(lambda v: f"{v:.2f}" if pd.notna(v) else '')

    raw.to_csv(DST, index=False)
    print(f"Saved harmonized data to {DST}  ({len(raw)} rows)")


if __name__ == '__main__':
    run_pipeline()
PYEOF

python3 /tmp/wq_harmonize.py
echo "Done. Harmonized water quality data written to $WATER_OUTPUT"
