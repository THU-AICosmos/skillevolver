"""
Tests for exoplanet period finding task (Kepler variant).

Verifies that the agent correctly identifies the exoplanet orbital period
from the Kepler-like light curve data.
"""

import os

import pytest


class TestExoplanetPeriod:
    """Test suite for the exoplanet period finding task."""

    # Expected period from the injected signal
    EXPECTED_PERIOD = 3.24176

    # Tolerance: ±0.01 days to account for numerical differences
    TOLERANCE = 0.01

    def get_period_path(self):
        """Find the period file in expected locations."""
        paths = ["/root/orbital_period.txt", "orbital_period.txt"]
        for path in paths:
            if os.path.exists(path):
                return path
        return None

    def test_period_file_exists(self):
        """Verify period file was created."""
        path = self.get_period_path()
        assert path is not None, "Period file not found. Expected /root/orbital_period.txt"

    def test_period_is_valid_number(self):
        """Verify period file contains a valid floating point number."""
        path = self.get_period_path()
        if path is None:
            pytest.skip("Period file not found")

        with open(path) as f:
            content = f.read().strip()

        try:
            period = float(content)
            assert period > 0, f"Period must be positive, got {period}"
        except ValueError:
            pytest.fail(f"Period '{content}' is not a valid number")

    def test_period_value_correct(self):
        """Verify the period value matches the expected result."""
        path = self.get_period_path()
        if path is None:
            pytest.skip("Period file not found")

        with open(path) as f:
            content = f.read().strip()

        period = float(content)

        # Check period matches expected value within tolerance
        assert abs(period - self.EXPECTED_PERIOD) < self.TOLERANCE, (
            f"Period {period:.4f} does not match expected {self.EXPECTED_PERIOD:.5f} "
            f"(tolerance: ±{self.TOLERANCE})"
        )

    def test_period_format(self):
        """Verify period is written with at most 4 decimal places."""
        path = self.get_period_path()
        if path is None:
            pytest.skip("Period file not found")

        with open(path) as f:
            content = f.read().strip()

        period = float(content)

        decimal_places = len(content.split(".")[-1]) if "." in content else 0
        assert decimal_places <= 4, (
            f"Period {period} should have at most 4 decimal places, got: {content} ({decimal_places} places)"
        )
