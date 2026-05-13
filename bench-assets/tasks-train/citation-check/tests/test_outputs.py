"""
Tests for citation-check training variant.

Verifies that the agent correctly identifies fabricated/hallucinated references
in the BibTeX bibliography file.
"""

import json
from pathlib import Path

import pytest

REPORT_FILE = Path("/root/verification_report.json")

# Expected fabricated references (titles, sorted alphabetically)
# These are papers with fake DOIs or that cannot be found in academic databases:
# 1. anderson2020graph - DOI 10.7654/ccr.2020.22.7.445 is fake (10.7654 is not a valid registrant)
# 2. chen2022quantum - DOI 10.9876/jqis.2022.8.2.77 is fake (10.9876 is not a valid registrant)
# 3. garcia2021reinforcement - DOI 10.4321/ral.2021.15.3.310 is fake (10.4321 is not a valid registrant)
# 4. nakamura2023federated - No DOI, generic author names, cannot be found in databases
EXPECTED_FABRICATED = [
    "Federated Learning Approaches for Privacy-Preserving Medical Imaging",
    "Graph Neural Networks for Drug Discovery and Molecular Property Prediction",
    "Quantum Error Correction Methods for Scalable Fault-Tolerant Computing",
    "Reinforcement Learning Strategies for Autonomous Warehouse Robotics",
]


class TestReportFileExists:
    """Test that the report file exists and is valid JSON."""

    def test_report_file_exists(self):
        """Verify the report file was created."""
        assert REPORT_FILE.exists(), f"Report file not found at {REPORT_FILE}"

    def test_report_file_valid_json(self):
        """Verify the report file contains valid JSON."""
        assert REPORT_FILE.exists(), "Report file does not exist"
        with open(REPORT_FILE) as f:
            try:
                json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"Report file is not valid JSON: {e}")

    def test_report_has_required_key(self):
        """Verify the report has the required 'suspicious_entries' key."""
        assert REPORT_FILE.exists(), "Report file does not exist"
        with open(REPORT_FILE) as f:
            data = json.load(f)
        assert "suspicious_entries" in data, "Missing required key: 'suspicious_entries'"

    def test_suspicious_entries_is_list(self):
        """Verify suspicious_entries is a list."""
        with open(REPORT_FILE) as f:
            data = json.load(f)
        assert isinstance(data["suspicious_entries"], list), "suspicious_entries should be a list"


class TestFabricatedReferencesDetected:
    """Test that all fabricated references are correctly identified."""

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        title = " ".join(title.split())
        return title.lower()

    def _get_detected_titles(self) -> list:
        """Get the list of detected fabricated reference titles."""
        with open(REPORT_FILE) as f:
            data = json.load(f)
        return data.get("suspicious_entries", [])

    def test_chen2022quantum_detected(self):
        """Verify the fabricated reference about quantum error correction is detected."""
        detected = self._get_detected_titles()
        detected_normalized = [self._normalize_title(t) for t in detected]
        expected = self._normalize_title("Quantum Error Correction Methods for Scalable Fault-Tolerant Computing")
        assert (
            expected in detected_normalized
        ), "Failed to detect fabricated reference: 'Quantum Error Correction Methods for Scalable Fault-Tolerant Computing'"

    def test_garcia2021reinforcement_detected(self):
        """Verify the fabricated reference about warehouse robotics is detected."""
        detected = self._get_detected_titles()
        detected_normalized = [self._normalize_title(t) for t in detected]
        expected = self._normalize_title("Reinforcement Learning Strategies for Autonomous Warehouse Robotics")
        assert expected in detected_normalized, "Failed to detect fabricated reference: 'Reinforcement Learning Strategies for Autonomous Warehouse Robotics'"

    def test_nakamura2023federated_detected(self):
        """Verify the fabricated reference about federated learning in medical imaging is detected."""
        detected = self._get_detected_titles()
        detected_normalized = [self._normalize_title(t) for t in detected]
        expected = self._normalize_title("Federated Learning Approaches for Privacy-Preserving Medical Imaging")
        assert expected in detected_normalized, "Failed to detect fabricated reference: 'Federated Learning Approaches for Privacy-Preserving Medical Imaging'"

    def test_anderson2020graph_detected(self):
        """Verify the fabricated reference about graph neural networks for drug discovery is detected."""
        detected = self._get_detected_titles()
        detected_normalized = [self._normalize_title(t) for t in detected]
        expected = self._normalize_title("Graph Neural Networks for Drug Discovery and Molecular Property Prediction")
        assert expected in detected_normalized, "Failed to detect fabricated reference: 'Graph Neural Networks for Drug Discovery and Molecular Property Prediction'"


class TestReferenceCount:
    """Test the count of detected fabricated references."""

    def test_correct_fabricated_count(self):
        """Verify exactly 4 fabricated references are detected."""
        with open(REPORT_FILE) as f:
            data = json.load(f)
        count = len(data.get("suspicious_entries", []))
        assert count == 4, f"Expected 4 fabricated references, but detected {count}"

    def test_no_empty_titles(self):
        """Verify no empty titles in the result."""
        with open(REPORT_FILE) as f:
            data = json.load(f)
        for title in data.get("suspicious_entries", []):
            assert title.strip(), "Found empty title in suspicious_entries"
