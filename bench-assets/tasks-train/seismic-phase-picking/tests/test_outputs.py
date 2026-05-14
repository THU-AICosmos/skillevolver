"""
Reduced test suite for seismic wave detection variant.
Tests P-wave precision and S-wave recall instead of F1 thresholds.
"""

from pathlib import Path

import pytest
from evaluate_picks import evaluate_predictions, load_labels, load_predictions

DETECTIONS_FILE = Path("/root/wave_detections.csv")
GROUND_TRUTH_FILE = Path(__file__).parent / "labels.csv"


@pytest.fixture(scope="module")
def metrics():
    """Load detections and ground truth, compute evaluation metrics."""
    if not DETECTIONS_FILE.exists():
        pytest.fail(f"Detection output not found: {DETECTIONS_FILE}")
    det_df = load_predictions(DETECTIONS_FILE)
    gt_df = load_labels(GROUND_TRUTH_FILE)
    return evaluate_predictions(det_df, gt_df, tolerance_samples=10)


def test_p_wave_precision(metrics):
    """P-wave precision must be at least 0.65."""
    p_prec = metrics["p_wave"]["precision"]
    assert p_prec >= 0.65, f"P-wave precision {p_prec:.3f} is below 0.65"


def test_s_wave_recall(metrics):
    """S-wave recall must be at least 0.45."""
    s_rec = metrics["s_wave"]["recall"]
    assert s_rec >= 0.45, f"S-wave recall {s_rec:.3f} is below 0.45"
