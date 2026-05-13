import os
import csv
import pytest


class TestOceanAcidificationAttribution:
    """Test cases for ocean acidification attribution task."""

    def test_ph_trend(self):
        """Check pH trend analysis output."""
        path = "/root/output/ph_trend.csv"
        assert os.path.exists(path), "ph_trend.csv not found"

        with open(path, 'r') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            slope = float(row['slope'])
            p_val = float(row['p_value'])
            assert -0.025 <= slope <= -0.012, f"Expected slope -0.025 to -0.012, got {slope}"
            assert p_val < 0.05, f"Expected p < 0.05, got {p_val}"

    def test_key_driver(self):
        """Check that Chemical is the dominant driver with ~48% contribution."""
        path = "/root/output/key_driver.csv"
        assert os.path.exists(path), "key_driver.csv not found"

        with open(path, 'r') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert row['category'].lower() == 'chemical'
            contrib = float(row['pct_contribution'])
            assert 35 <= contrib <= 60, f"Expected 35-60%, got {contrib}%"
