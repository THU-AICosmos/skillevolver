"""
Test suite for gravitational wave signal characterization task.
Verifies that the agent correctly identified the best-fit waveform templates
and component masses.
"""

from pathlib import Path
from typing import ClassVar

import pandas as pd
import pytest

RESULT_PATH = Path("/root/signal_analysis.csv")
REFERENCE_PATH = Path("/tests/expected_results.csv")


class TestSignalCharacterization:
    """Validate the signal characterization output."""

    SNR_TOL = 0.25
    MASS_TOL = 0.1

    REQUIRED_MODELS: ClassVar[set[str]] = {"IMRPhenomD", "TaylorT4"}
    MASS_LO = 15
    MASS_HI = 35

    @pytest.fixture
    def results(self):
        """Load agent results CSV."""
        if not RESULT_PATH.exists():
            pytest.skip(f"Result file {RESULT_PATH} not found")
        try:
            return pd.read_csv(RESULT_PATH)
        except Exception as e:
            pytest.fail(f"Cannot parse result file: {e}")

    @pytest.fixture
    def reference(self):
        """Load reference results CSV."""
        if not REFERENCE_PATH.exists():
            pytest.skip(f"Reference file {REFERENCE_PATH} not found")
        try:
            return pd.read_csv(REFERENCE_PATH)
        except Exception as e:
            pytest.fail(f"Cannot parse reference file: {e}")

    def test_result_file_present(self):
        """The output CSV must exist."""
        assert RESULT_PATH.exists(), f"Expected output at {RESULT_PATH}"

    def test_columns_correct(self, results):
        """Output must have the four required columns."""
        needed = {"waveform_model", "peak_snr", "mass1", "mass2"}
        present = set(results.columns)
        missing = needed - present
        assert not missing, f"Missing columns: {missing}. Found: {list(results.columns)}"

    def test_exactly_two_rows(self, results):
        """There should be exactly one row per waveform model."""
        assert len(results) == len(self.REQUIRED_MODELS), (
            f"Expected {len(self.REQUIRED_MODELS)} rows, got {len(results)}"
        )

    def test_models_present(self, results):
        """Both required waveform models must appear."""
        found = set(results["waveform_model"].dropna().unique())
        missing = self.REQUIRED_MODELS - found
        assert not missing, f"Missing waveform models: {missing}"
        extra = found - self.REQUIRED_MODELS
        assert not extra, f"Unexpected waveform models: {extra}"

    def test_mass_values_in_range(self, results):
        """Component masses must fall within the search grid."""
        for _, row in results.iterrows():
            m1 = row["mass1"]
            m2 = row["mass2"]
            assert self.MASS_LO <= m1 <= self.MASS_HI, (
                f"{row['waveform_model']}: mass1={m1} outside [{self.MASS_LO},{self.MASS_HI}]"
            )
            assert self.MASS_LO <= m2 <= self.MASS_HI, (
                f"{row['waveform_model']}: mass2={m2} outside [{self.MASS_LO},{self.MASS_HI}]"
            )
            assert m1 >= m2, (
                f"{row['waveform_model']}: mass1={m1} should be >= mass2={m2}"
            )

    def test_matches_reference(self, results, reference):
        """Agent results must match reference values within tolerance."""
        agent_lookup = {
            row["waveform_model"]: row
            for _, row in results.iterrows()
            if pd.notna(row["waveform_model"])
        }

        errors = []
        for _, ref_row in reference.iterrows():
            model = ref_row["waveform_model"]
            if model not in agent_lookup:
                errors.append(f"{model}: not found in agent output")
                continue

            agent_row = agent_lookup[model]

            snr_diff = abs(agent_row["peak_snr"] - ref_row["peak_snr"])
            if snr_diff > self.SNR_TOL:
                errors.append(
                    f"{model}: peak_snr {agent_row['peak_snr']:.4f} vs expected "
                    f"{ref_row['peak_snr']:.4f} (diff={snr_diff:.4f} > tol={self.SNR_TOL})"
                )
                continue

            m1_diff = abs(agent_row["mass1"] - ref_row["mass1"])
            if m1_diff > self.MASS_TOL:
                errors.append(
                    f"{model}: mass1 {agent_row['mass1']} vs expected {ref_row['mass1']}"
                )
                continue

            m2_diff = abs(agent_row["mass2"] - ref_row["mass2"])
            if m2_diff > self.MASS_TOL:
                errors.append(
                    f"{model}: mass2 {agent_row['mass2']} vs expected {ref_row['mass2']}"
                )
                continue

        if errors:
            pytest.fail("Mismatches:\n" + "\n".join(errors))
