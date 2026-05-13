"""
Video Tutorial Milestone Locator - Test Suite

Validates the output of the milestone locator task.
Contains 2 tests:
1. test_milestone_format: Checks file existence, JSON structure, and label correctness
2. test_timestamp_accuracy: Checks temporal accuracy using median error and coverage metrics

All metrics are deterministic and reproducible (no LLM-as-judge).
"""

import json
from pathlib import Path

import numpy as np
import pytest

RESULT_PATH = Path("/root/video_milestones.json")
REFERENCE_PATH = Path(__file__).parent / "ground_truth.json"

MILESTONE_LABELS = [
    "What we'll do",
    "Getting started",
    "Import your plan into Blender",
    "It all starts with a plane",
    "Getting the plan in place",
    "Tracing inner walls",
    "Continue tracing inner walls",
    "Make the floor",
    "Extruding the walls in Z",
    "Fixing face orientation errors",
    "Save As",
    "Great job!",
]


@pytest.fixture(scope="session")
def result_data():
    """Load the generated milestones file."""
    with open(RESULT_PATH) as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def reference_data():
    """Load the ground-truth milestones."""
    with open(REFERENCE_PATH) as fh:
        return json.load(fh)


# ============================================================================
# Test 1: Milestone Format and Labels
# ============================================================================


def test_milestone_format(result_data):
    """
    Verify the output file has the expected schema and labels.

    Checks:
    1. File exists at the expected path
    2. Top-level keys 'metadata' and 'milestones' are present
    3. Exactly 12 milestones
    4. Each milestone has 'timestamp' (numeric) and 'label' (string)
    5. Labels match the expected list in order
    """
    assert RESULT_PATH.exists(), f"Output not found: {RESULT_PATH}"

    assert "metadata" in result_data, "Missing 'metadata' key"
    assert "milestones" in result_data, "Missing 'milestones' key"

    ms_list = result_data["milestones"]
    assert len(ms_list) == 12, f"Expected 12 milestones, found {len(ms_list)}"

    for idx, entry in enumerate(ms_list):
        assert "timestamp" in entry, f"Milestone {idx+1} missing 'timestamp'"
        assert "label" in entry, f"Milestone {idx+1} missing 'label'"
        assert isinstance(entry["timestamp"], (int, float)), (
            f"Milestone {idx+1} timestamp must be numeric"
        )
        assert isinstance(entry["label"], str), (
            f"Milestone {idx+1} label must be a string"
        )

    for idx, (entry, expected_label) in enumerate(zip(ms_list, MILESTONE_LABELS)):
        assert entry["label"] == expected_label, (
            f"Milestone {idx+1}: expected '{expected_label}', got '{entry['label']}'"
        )


# ============================================================================
# Test 2: Timestamp Accuracy
# ============================================================================


def test_timestamp_accuracy(result_data, reference_data):
    """
    Verify timestamps are close to the ground truth.

    Metrics (different from the original test suite):
    1. Median Absolute Error (MedAE) <= 20 seconds
    2. At least 50% of milestones within 15 seconds of ground truth

    Oracle performance:
    - MedAE: ~0s
    - Coverage @15s: 100%
    """
    pred_ms = result_data["milestones"]
    ref_ms = reference_data["milestones"]

    deviations = []
    for p, r in zip(pred_ms, ref_ms):
        deviations.append(abs(p["timestamp"] - r["timestamp"]))

    med_err = float(np.median(deviations))
    assert med_err <= 20.0, (
        f"Median Absolute Error is {med_err:.2f}s, must be <= 20s"
    )

    within_15 = float(np.mean([d <= 15 for d in deviations]))
    assert within_15 >= 0.50, (
        f"Only {within_15*100:.1f}% milestones within 15s of ground truth, need >= 50%"
    )

    print(f"\nTimestamp Accuracy Report:")
    print(f"  Median AE : {med_err:.2f}s")
    print(f"  Coverage @15s: {within_15*100:.1f}%")
    print(f"  Max deviation: {max(deviations):.2f}s")
