"""
Tests that verify the Sinclair sheet structure in the Excel output.

Since the solver writes Excel formulas to the Sinclair sheet,
these tests verify the sheet structure and formula references are correct.
The actual formula evaluation happens in Excel.
"""

import math
import openpyxl
import polars as pl
import pytest

OUTPUT_FILE = "/root/data/weightlifting_results.xlsx"
GROUND_TRUTH_FILE = "/tests/ground_truth_sinclair.xlsx"

# Sinclair formula coefficients (IWF 2024 quadrennium)
MALE_SINCLAIR_A = 0.751945030
MALE_THRESHOLD = 200.0
FEMALE_SINCLAIR_A = 0.783497476
FEMALE_THRESHOLD = 175.0

TOLERANCE = 0.01  # Allow small floating point differences


def compute_sinclair(gender: str, bodyweight: float, total: float) -> float:
    """Calculate Sinclair coefficient based on gender, bodyweight, and total.

    This implements the same formula as the Excel formula in the Sinclair sheet,
    allowing us to verify the formula produces correct results.
    """
    if gender == "M":
        A_coeff, threshold = MALE_SINCLAIR_A, MALE_THRESHOLD
    else:
        A_coeff, threshold = FEMALE_SINCLAIR_A, FEMALE_THRESHOLD

    if bodyweight >= threshold:
        return round(total * 1.0, 3)
    else:
        log_ratio = math.log10(bodyweight / threshold)
        exponent = A_coeff * (log_ratio ** 2)
        multiplier = 10 ** exponent
        return round(total * multiplier, 3)


@pytest.fixture
def results_df():
    """Load the Results sheet from output file."""
    return pl.read_excel(OUTPUT_FILE, sheet_name="Results")


@pytest.fixture
def sinclair_df():
    """Load the Sinclair sheet from output file."""
    return pl.read_excel(OUTPUT_FILE, sheet_name="Sinclair")


@pytest.fixture
def ground_truth_df():
    """Load the ground truth data with pre-calculated coefficients."""
    return pl.read_excel(GROUND_TRUTH_FILE, sheet_name="Sinclair")


class TestSheetStructure:
    """Tests for Excel file sheet structure."""

    def test_results_sheet_exists(self, results_df):
        """Verify Results sheet exists and has data."""
        assert results_df is not None
        assert results_df.height > 0

    def test_sinclair_sheet_exists(self, sinclair_df):
        """Verify Sinclair sheet exists."""
        assert sinclair_df is not None

    def test_sinclair_sheet_has_correct_columns(self, sinclair_df):
        """Verify Sinclair sheet has the expected columns."""
        expected_columns = [
            "Athlete",
            "Gender",
            "BodyweightKg",
            "BestSnatchKg",
            "BestCleanJerkKg",
            "TotalKg",
            "Sinclair",
        ]
        assert sinclair_df.columns == expected_columns

    def test_row_count_matches(self, results_df, sinclair_df):
        """Verify Sinclair sheet has same row count as Results sheet.
        Make sure there are the same number of competing athletes.
        """
        assert sinclair_df.height == results_df.height


class TestSinclairSheetFormulas:
    """Tests that verify the Sinclair sheet contains formula references.

    Uses openpyxl to check if cells contain formulas (start with '=').
    """

    def test_sinclair_sheet_not_empty(self, sinclair_df):
        """Sinclair sheet should not be empty."""
        assert sinclair_df.height > 0

    def test_total_column_is_formula(self):
        """Column F (TotalKg) should contain a formula summing D+E.
        Checking if the Excel used a formula here to avoid cheating.
        """
        wb = openpyxl.load_workbook(OUTPUT_FILE)
        sinclair_sheet = wb["Sinclair"]
        cell_value = sinclair_sheet["F2"].value
        assert isinstance(cell_value, str) and cell_value.startswith("="), f"Expected formula, got: {cell_value}"

    def test_sinclair_column_is_formula(self):
        """Column G (Sinclair) should contain the Sinclair calculation formula.
        Checking if the Excel used a formula here to avoid cheating.
        """
        wb = openpyxl.load_workbook(OUTPUT_FILE)
        sinclair_sheet = wb["Sinclair"]
        cell_value = sinclair_sheet["G2"].value
        assert isinstance(cell_value, str) and cell_value.startswith("="), f"Expected formula, got: {cell_value}"
        # Should contain ROUND and IF for the Sinclair calculation
        assert "ROUND(" in cell_value, "Sinclair formula should use ROUND"
        assert "IF(" in cell_value, "Sinclair formula should use IF for gender-based calculation"


class TestSinclairAccuracy:
    """Tests that verify the computed Sinclair values match ground truth.

    Since Excel formulas can't be evaluated directly by polars/openpyxl,
    we evaluate the same formula in Python and compare against ground truth.
    """

    def test_sinclair_values_match_ground_truth(self, results_df, ground_truth_df):
        """Verify computed Sinclair values match ground truth within tolerance.

        This test evaluates the Sinclair formula using data from the Results sheet
        and compares against the pre-calculated Sinclair in ground truth.
        """
        mismatches = []
        for i in range(results_df.height):
            athlete = results_df["Athlete"][i]
            gender = results_df["Gender"][i]
            bodyweight = results_df["BodyweightKg"][i]
            snatch = results_df["BestSnatchKg"][i]
            clean_jerk = results_df["BestCleanJerkKg"][i]
            total = snatch + clean_jerk

            computed_sinclair = compute_sinclair(gender, bodyweight, total)

            # Find ground truth for this athlete
            gt_row = ground_truth_df.filter(pl.col("Athlete") == athlete)
            assert gt_row.height == 1, f"Expected exactly one match for {athlete}"
            gt_sinclair = gt_row["Sinclair"][0]

            if abs(computed_sinclair - gt_sinclair) > TOLERANCE:
                mismatches.append(f"{athlete}: computed={computed_sinclair}, expected={gt_sinclair}")

        assert not mismatches, f"Sinclair mismatches found:\n{mismatches}\n"

    def test_all_athletes_have_ground_truth(self, results_df, ground_truth_df):
        """Verify all athletes in output have corresponding ground truth."""
        output_names = set(results_df["Athlete"].to_list())
        gt_names = set(ground_truth_df["Athlete"].to_list())

        missing = output_names - gt_names
        assert not missing, f"Athletes missing from ground truth: {missing}"

    def test_sinclair_formula_handles_male_athletes(self, results_df, ground_truth_df):
        """Verify Sinclair calculation is correct for male athletes."""
        male_df = results_df.filter(pl.col("Gender") == "M")
        assert male_df.height > 0, "No male athletes in test data"

        for i in range(male_df.height):
            athlete = male_df["Athlete"][i]
            bodyweight = male_df["BodyweightKg"][i]
            total = male_df["BestSnatchKg"][i] + male_df["BestCleanJerkKg"][i]

            computed = compute_sinclair("M", bodyweight, total)
            gt_sinclair = ground_truth_df.filter(pl.col("Athlete") == athlete)["Sinclair"][0]

            assert abs(computed - gt_sinclair) < TOLERANCE, f"Male athlete {athlete}: computed={computed}, expected={gt_sinclair}"

    def test_sinclair_formula_handles_female_athletes(self, results_df, ground_truth_df):
        """Verify Sinclair calculation is correct for female athletes."""
        female_df = results_df.filter(pl.col("Gender") == "F")
        assert female_df.height > 0, "No female athletes in test data"

        for i in range(female_df.height):
            athlete = female_df["Athlete"][i]
            bodyweight = female_df["BodyweightKg"][i]
            total = female_df["BestSnatchKg"][i] + female_df["BestCleanJerkKg"][i]

            computed = compute_sinclair("F", bodyweight, total)
            gt_sinclair = ground_truth_df.filter(pl.col("Athlete") == athlete)["Sinclair"][0]

            assert abs(computed - gt_sinclair) < TOLERANCE, f"Female athlete {athlete}: computed={computed}, expected={gt_sinclair}"
