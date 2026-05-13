import csv
import os

import pytest


class TestWisconsinFloodDetection:
    """Test cases for Wisconsin flood-stage exceedance detection (Apr 22-28, 2025)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.csv_path = "/root/output/flood_results.csv"
        self.results = {}
        if os.path.exists(self.csv_path):
            with open(self.csv_path, "r") as fh:
                for row in csv.DictReader(fh):
                    self.results[row["station_id"]] = int(row["flood_days"])

    def test_csv_output_exists(self):
        assert os.path.exists(self.csv_path), \
            "CSV file not found at /root/output/flood_results.csv"

    def test_correct_stations_and_flood_days(self):
        expected = {
            "05365500": 8,
            "05367500": 8,
            "05344500": 8,
            "05340500": 8,
            "05370000": 8,
            "05402000": 1,
            "05382000": 1,
        }
        assert self.results == expected, \
            f"Expected {expected}, got {self.results}"
