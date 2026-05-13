import json
from pathlib import Path

import pytest

SUMMARY = Path("/app/summary.json")
EXPECTED = Path(__file__).parent / "expected.json"
TOLERANCE = 0


@pytest.fixture
def summary():
    assert SUMMARY.exists(), f"Missing {SUMMARY}"
    return json.loads(SUMMARY.read_text())


@pytest.fixture
def expected():
    return json.loads(EXPECTED.read_text())


class TestPulls:
    def test_count(self, summary, expected):
        assert abs(summary["pulls"]["count"] - expected["pulls"]["count"]) <= TOLERANCE

    def test_merged_count(self, summary, expected):
        assert abs(summary["pulls"]["merged_count"] - expected["pulls"]["merged_count"]) <= TOLERANCE

    def test_open_count(self, summary, expected):
        assert abs(summary["pulls"]["open_count"] - expected["pulls"]["open_count"]) <= TOLERANCE

    def test_mean_merge_days(self, summary, expected):
        assert abs(summary["pulls"]["mean_merge_days"] - expected["pulls"]["mean_merge_days"]) <= 0.5

    def test_most_active_author(self, summary, expected):
        assert summary["pulls"]["most_active_author"] == expected["pulls"]["most_active_author"]


class TestIssues:
    def test_count(self, summary, expected):
        assert abs(summary["issues"]["count"] - expected["issues"]["count"]) <= TOLERANCE

    def test_bugs(self, summary, expected):
        assert abs(summary["issues"]["bugs"] - expected["issues"]["bugs"]) <= TOLERANCE

    def test_open_bugs(self, summary, expected):
        assert abs(summary["issues"]["open_bugs"] - expected["issues"]["open_bugs"]) <= TOLERANCE
