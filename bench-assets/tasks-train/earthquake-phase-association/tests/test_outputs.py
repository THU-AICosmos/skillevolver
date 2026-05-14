"""
Tests for the seismic event detection task.
Evaluates precision of the detected event catalog against the reference catalog.
"""

import pytest
from test_utils import TIME_THRESHOLD, calc_detection_performance, filter_catalog, load_catalog


def test_precision_above_threshold():
    """Test that detection precision exceeds 0.5."""
    detected_csv = "/root/event_catalog.csv"
    reference_csv = "/tests/catalog.csv"
    t_start = "2019-07-04T19:00:00"
    t_end = "2019-07-04T20:00:00"

    t_detected, _ = filter_catalog(load_catalog(detected_csv), t_start, t_end)
    t_reference, _ = filter_catalog(load_catalog(reference_csv), t_start, t_end)
    recall, precision, f1 = calc_detection_performance(t_detected, t_reference, TIME_THRESHOLD)

    print(f"Recall: {recall:.3f}")
    print(f"Precision: {precision:.3f}")
    print(f"F1: {f1:.3f}")

    assert precision > 0.5, (
        f"Precision {precision:.3f} does not exceed 0.5 "
        f"(recall={recall:.3f}, f1={f1:.3f})"
    )
