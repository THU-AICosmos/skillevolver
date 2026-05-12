import os
import csv
import pytest


class TestActionStageDetection:
    """Test cases for Ohio action stage exceedance detection task."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Load output file if it exists."""
        self.csv_path = "/root/output/action_stage_results.csv"
        self.results = {}

        if os.path.exists(self.csv_path):
            with open(self.csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.results[row['station_id']] = int(row['action_days'])

    def test_csv_output_exists(self):
        """Check that CSV output file was created."""
        assert os.path.exists(self.csv_path), \
            "CSV file not found at /root/output/action_stage_results.csv"

    def test_correct_stations_and_action_days(self):
        """Check that all stations and action days are correct."""
        expected = {
            '03124000': 9,
            '03220000': 9,
            '03264000': 9,
            '03130000': 9,
            '03225500': 9,
            '03267900': 9,
            '03109500': 9,
            '03144000': 9,
            '03232000': 9,
            '03102500': 9,
            '03234500': 9,
            '03102950': 9,
            '03120500': 9,
            '03133500': 9,
            '03126000': 9,
            '03229500': 9,
            '03157000': 9,
            '03092090': 9,
            '03141500': 9,
            '03128500': 9,
            '03127000': 9,
            '03110000': 9,
            '03217500': 2,
            '03245500': 1
        }

        assert self.results == expected, \
            f"Expected {expected}, got {self.results}"
