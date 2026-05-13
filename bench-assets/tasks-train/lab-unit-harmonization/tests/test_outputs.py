#!/usr/bin/env python3
"""
Test suite for water quality unit harmonization task.

=============================================================================
TEST STRUCTURE (42 total tests)
=============================================================================

BASIC TESTS (7 tests) - Verify fundamental output requirements:
  1. test_file_exists           - Output file was created
  2. test_has_expected_columns  - All 50 parameter columns present
  3. test_format_two_decimals   - All values have X.XX format
  4. test_no_whitespace         - No leading/trailing whitespace
  5. test_no_invalid_chars      - No commas, scientific notation, letters
  6. test_no_conversion_params_in_range - 15 parameters that don't need
     unit conversion (same units or dimensionless)
  7. test_no_missing_values     - No missing/empty values in output

CONVERSION PARAMETER TESTS (35 parametrized tests) - Core task evaluation:
  8-42. test_conversion_param_in_range[*] - One test per parameter that
        requires unit conversion between alternative measurement systems.

REWARD CALCULATION:
  reward = passed_tests / total_tests (42)
=============================================================================
"""

import pandas as pd
import numpy as np
import re
import os
import pytest

# Paths
HARMONIZED_FILE = "/root/water_quality_harmonized.csv"

# Parameters WITHOUT unit conversion (15 parameters)
NO_CONVERSION_PARAMS = [
    'pH',
    'Turbidity_NTU',
    'Conductivity_uS_cm',
    'Temperature_C',
    'Dissolved_Oxygen_Pct',
    'UV254_Absorbance',
    'ORP_mV',
    'Color_PCU',
    'Odor_TON',
    'Total_Coliform_CFU',
    'E_Coli_CFU',
    'Fecal_Coliform_CFU',
    'BOD5_mg_L',
    'COD_mg_L',
    'Chlorophyll_a_ug_L',
]

# Parameters WITH unit conversion (35 parameters)
CONVERSION_PARAMS = [
    'Dissolved_Oxygen_mg_L',
    'Nitrate_N_mg_L',
    'Nitrite_N_mg_L',
    'Ammonia_N_mg_L',
    'Total_Kjeldahl_N_mg_L',
    'Total_Phosphorus_mg_L',
    'Orthophosphate_mg_L',
    'Sulfate_mg_L',
    'Chloride_mg_L',
    'Fluoride_mg_L',
    'Calcium_mg_L',
    'Magnesium_mg_L',
    'Sodium_mg_L',
    'Potassium_mg_L',
    'Hardness_CaCO3_mg_L',
    'Alkalinity_CaCO3_mg_L',
    'Lead_ug_L',
    'Mercury_ug_L',
    'Cadmium_ug_L',
    'Arsenic_ug_L',
    'Chromium_ug_L',
    'Copper_ug_L',
    'Zinc_ug_L',
    'Nickel_ug_L',
    'Selenium_ug_L',
    'Manganese_ug_L',
    'Iron_ug_L',
    'Barium_ug_L',
    'Total_THM_ug_L',
    'Benzene_ug_L',
    'Toluene_ug_L',
    'TDS_mg_L',
    'TSS_mg_L',
    'Total_Nitrogen_mg_L',
    'Silica_mg_L',
]

# All parameter columns
PARAM_COLUMNS = NO_CONVERSION_PARAMS + CONVERSION_PARAMS

# Reference ranges for all parameters
REFERENCE = {
    # No-conversion parameters
    'pH': {'min': 6.0, 'max': 9.0},
    'Turbidity_NTU': {'min': 0.1, 'max': 500.0},
    'Conductivity_uS_cm': {'min': 10.0, 'max': 5000.0},
    'Temperature_C': {'min': 0.5, 'max': 40.0},
    'Dissolved_Oxygen_Pct': {'min': 10.0, 'max': 200.0},
    'UV254_Absorbance': {'min': 0.0, 'max': 2.0},
    'ORP_mV': {'min': -500.0, 'max': 800.0},
    'Color_PCU': {'min': 1.0, 'max': 500.0},
    'Odor_TON': {'min': 1.0, 'max': 200.0},
    'Total_Coliform_CFU': {'min': 0.0, 'max': 50000.0},
    'E_Coli_CFU': {'min': 0.0, 'max': 10000.0},
    'Fecal_Coliform_CFU': {'min': 0.0, 'max': 20000.0},
    'BOD5_mg_L': {'min': 0.5, 'max': 300.0},
    'COD_mg_L': {'min': 1.0, 'max': 1000.0},
    'Chlorophyll_a_ug_L': {'min': 0.1, 'max': 500.0},

    # Conversion parameters (min=0.0 for parameters that can have non-detect/zero values)
    'Dissolved_Oxygen_mg_L': {'min': 1.0, 'max': 20.0},
    'Nitrate_N_mg_L': {'min': 0.0, 'max': 50.0},
    'Nitrite_N_mg_L': {'min': 0.0, 'max': 5.0},
    'Ammonia_N_mg_L': {'min': 0.0, 'max': 30.0},
    'Total_Kjeldahl_N_mg_L': {'min': 0.0, 'max': 50.0},
    'Total_Phosphorus_mg_L': {'min': 0.0, 'max': 20.0},
    'Orthophosphate_mg_L': {'min': 0.0, 'max': 10.0},
    'Sulfate_mg_L': {'min': 0.0, 'max': 1000.0},
    'Chloride_mg_L': {'min': 1.0, 'max': 1000.0},
    'Fluoride_mg_L': {'min': 0.0, 'max': 10.0},
    'Calcium_mg_L': {'min': 1.0, 'max': 500.0},
    'Magnesium_mg_L': {'min': 0.0, 'max': 200.0},
    'Sodium_mg_L': {'min': 1.0, 'max': 1000.0},
    'Potassium_mg_L': {'min': 0.0, 'max': 50.0},
    'Hardness_CaCO3_mg_L': {'min': 5.0, 'max': 1500.0},
    'Alkalinity_CaCO3_mg_L': {'min': 5.0, 'max': 500.0},
    'Lead_ug_L': {'min': 0.0, 'max': 500.0},
    'Mercury_ug_L': {'min': 0.0, 'max': 50.0},
    'Cadmium_ug_L': {'min': 0.0, 'max': 100.0},
    'Arsenic_ug_L': {'min': 0.0, 'max': 500.0},
    'Chromium_ug_L': {'min': 0.0, 'max': 500.0},
    'Copper_ug_L': {'min': 0.0, 'max': 5000.0},
    'Zinc_ug_L': {'min': 0.0, 'max': 10000.0},
    'Nickel_ug_L': {'min': 0.0, 'max': 1000.0},
    'Selenium_ug_L': {'min': 0.0, 'max': 200.0},
    'Manganese_ug_L': {'min': 0.0, 'max': 5000.0},
    'Iron_ug_L': {'min': 5.0, 'max': 50000.0},
    'Barium_ug_L': {'min': 1.0, 'max': 5000.0},
    'Total_THM_ug_L': {'min': 0.0, 'max': 500.0},
    'Benzene_ug_L': {'min': 0.0, 'max': 100.0},
    'Toluene_ug_L': {'min': 0.0, 'max': 2000.0},
    'TDS_mg_L': {'min': 0.0, 'max': 10000.0},
    'TSS_mg_L': {'min': 0.0, 'max': 5000.0},
    'Total_Nitrogen_mg_L': {'min': 0.1, 'max': 100.0},
    'Silica_mg_L': {'min': 0.5, 'max': 100.0},
}


def is_within_range(value, min_val, max_val):
    """Check if a numeric value falls within the expected range."""
    if pd.isna(value):
        return True
    try:
        num = float(value)
        return min_val <= num <= max_val
    except (ValueError, TypeError):
        return False


class TestHarmonizedOutput:
    """Test suite for harmonized water quality data output."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Load harmonized data."""
        if os.path.exists(HARMONIZED_FILE):
            self.df = pd.read_csv(HARMONIZED_FILE, dtype=str)
        else:
            self.df = None

    # -------------------------------------------------------------------------
    # Test 1: File exists
    # -------------------------------------------------------------------------
    def test_file_exists(self):
        """Test that harmonized output file exists."""
        assert os.path.exists(HARMONIZED_FILE), f"Harmonized file not found: {HARMONIZED_FILE}"

    # -------------------------------------------------------------------------
    # Test 2: Has expected columns
    # -------------------------------------------------------------------------
    def test_has_expected_columns(self):
        """Test that all 50 expected parameter columns are present."""
        assert self.df is not None, "Harmonized file not loaded"
        missing_cols = [col for col in PARAM_COLUMNS if col not in self.df.columns]
        assert len(missing_cols) == 0, f"Missing columns ({len(missing_cols)}): {missing_cols}"

    # -------------------------------------------------------------------------
    # Test 3: All values have exactly 2 decimal places
    # -------------------------------------------------------------------------
    def test_format_two_decimals(self):
        """Test that all values have exactly 2 decimal places (X.XX format)."""
        assert self.df is not None, "Harmonized file not loaded"

        pattern = r'^-?\d+\.\d{2}$'
        errors = []

        for column in PARAM_COLUMNS:
            if column not in self.df.columns:
                continue
            for idx, value in self.df[column].items():
                if pd.isna(value):
                    continue
                if not re.match(pattern, str(value)):
                    errors.append((column, idx, value))
                    if len(errors) >= 10:
                        break
            if len(errors) >= 10:
                break

        if errors:
            pytest.fail(f"Values without 2 decimal places: {errors[:5]}")

    # -------------------------------------------------------------------------
    # Test 4: No whitespace in values
    # -------------------------------------------------------------------------
    def test_no_whitespace(self):
        """Test that no values contain leading/trailing whitespace."""
        assert self.df is not None, "Harmonized file not loaded"

        errors = []
        for column in PARAM_COLUMNS:
            if column not in self.df.columns:
                continue
            for idx, value in self.df[column].items():
                if pd.isna(value):
                    continue
                s = str(value)
                if s != s.strip():
                    errors.append((column, idx, repr(value)))
                    if len(errors) >= 10:
                        break
            if len(errors) >= 10:
                break

        if errors:
            pytest.fail(f"Values with whitespace: {errors[:5]}")

    # -------------------------------------------------------------------------
    # Test 5: No invalid characters
    # -------------------------------------------------------------------------
    def test_no_invalid_chars(self):
        """Test that values contain only valid characters (digits, decimal point, minus sign)."""
        assert self.df is not None, "Harmonized file not loaded"

        errors = []

        for column in PARAM_COLUMNS:
            if column not in self.df.columns:
                continue
            for idx, value in self.df[column].items():
                if pd.isna(value):
                    continue
                s = str(value)
                if ',' in s or 'e' in s.lower() or any(c.isalpha() for c in s):
                    errors.append((column, idx, value))
                    if len(errors) >= 10:
                        break
            if len(errors) >= 10:
                break

        if errors:
            pytest.fail(f"Values with invalid characters: {errors[:5]}")

    # -------------------------------------------------------------------------
    # Test 6: No-conversion parameters within range (single test for 15 params)
    # -------------------------------------------------------------------------
    def test_no_conversion_params_in_range(self):
        """
        Test that all 15 parameters WITHOUT unit conversion have values within expected range.
        These parameters use same units across all measurement systems.
        """
        assert self.df is not None, "Harmonized file not loaded"

        all_errors = {}

        for column in NO_CONVERSION_PARAMS:
            if column not in self.df.columns:
                continue
            if column not in REFERENCE:
                continue

            min_val = REFERENCE[column]['min']
            max_val = REFERENCE[column]['max']

            col_errors = []
            for idx, value in self.df[column].items():
                if not is_within_range(value, min_val, max_val):
                    col_errors.append((idx, value))

            if col_errors:
                all_errors[column] = {
                    'range': f"[{min_val}, {max_val}]",
                    'errors': col_errors[:3]
                }

        if all_errors:
            error_summary = "; ".join([
                f"{col}: {info['errors'][:2]}"
                for col, info in list(all_errors.items())[:5]
            ])
            pytest.fail(f"Range errors in {len(all_errors)} no-conversion params: {error_summary}")

    # -------------------------------------------------------------------------
    # Test 7: No missing values
    # -------------------------------------------------------------------------
    def test_no_missing_values(self):
        """Test that harmonized output has no missing or empty values."""
        assert self.df is not None, "Harmonized file not loaded"

        errors = []

        for column in PARAM_COLUMNS:
            if column not in self.df.columns:
                continue

            for idx, value in self.df[column].items():
                if pd.isna(value):
                    errors.append((column, idx, "NaN"))
                    if len(errors) >= 20:
                        break
                elif str(value).strip() in ['', 'NaN', 'None', 'nan', 'none']:
                    errors.append((column, idx, repr(value)))
                    if len(errors) >= 20:
                        break

            if len(errors) >= 20:
                break

        if errors:
            error_summary = f"Found {len(errors)} missing values in output. Examples: {errors[:5]}"
            pytest.fail(error_summary)

    # -------------------------------------------------------------------------
    # Tests 8-42: Conversion parameters within range (35 parametrized tests)
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize("column", CONVERSION_PARAMS)
    def test_conversion_param_in_range(self, column):
        """
        Test that a parameter WITH unit conversion has values within expected range.
        These parameters require conversion between alternative measurement units.
        """
        assert self.df is not None, "Harmonized file not loaded"

        if column not in self.df.columns:
            pytest.skip(f"Column {column} not in dataframe")

        if column not in REFERENCE:
            pytest.skip(f"Column {column} not in reference")

        min_val = REFERENCE[column]['min']
        max_val = REFERENCE[column]['max']

        out_of_range = []
        for idx, value in self.df[column].items():
            if not is_within_range(value, min_val, max_val):
                out_of_range.append((idx, value))

        if out_of_range:
            error_msg = f"Range errors in {column} (expected [{min_val}, {max_val}]): {out_of_range[:5]}"
            pytest.fail(error_msg)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
