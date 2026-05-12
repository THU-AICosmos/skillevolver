"""
Use this file to define pytest tests that verify the outputs of the task.

This file will be copied to /tests/test_outputs.py and run by the /tests/test.sh file
from the working directory.
"""

import pytest
from test_utils import TIME_THRESHOLD, calc_detection_performance, filter_catalog, load_catalog


def test_f1_above_minimum():
    """Test that the F1 score exceeds the minimum acceptable threshold of 0.4."""
    catalog_csv = "/root/earthquake_catalog.csv"
    reference_csv = "/tests/catalog.csv"
    start_datetime = "2019-07-04T19:00:00"
    end_datetime = "2019-07-04T20:00:00"

    t_detected, _ = filter_catalog(load_catalog(catalog_csv, time_col="event_time"), start_datetime, end_datetime)
    t_reference, _ = filter_catalog(load_catalog(reference_csv), start_datetime, end_datetime)
    recall, precision, f1 = calc_detection_performance(t_detected, t_reference, TIME_THRESHOLD)

    print(f"Precision: {precision:.3f}")
    print(f"Recall: {recall:.3f}")
    print(f"F1: {f1:.3f}")

    assert f1 > 0.4, f"F1 score {f1:.3f} is not greater than 0.4 with precision {precision:.3f} and recall {recall:.3f}"


def test_minimum_event_count():
    """Test that at least 50 events were detected in the evaluation window."""
    catalog_csv = "/root/earthquake_catalog.csv"
    start_datetime = "2019-07-04T19:00:00"
    end_datetime = "2019-07-04T20:00:00"

    t_detected, detected_catalog = filter_catalog(
        load_catalog(catalog_csv, time_col="event_time"), start_datetime, end_datetime
    )

    num_events = len(t_detected)
    print(f"Number of detected events: {num_events}")

    assert num_events >= 50, f"Only {num_events} events detected, need at least 50"
