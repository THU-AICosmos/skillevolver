"""
Test suite for lecture video content analyzer task.

Validates the content analysis report and trimmed video output.
"""

import json
import os
import subprocess

import pytest


ANALYSIS_PATH = "content_analysis.json"
TRIMMED_VIDEO_PATH = "trimmed_lecture.mp4"
INPUT_VIDEO_PATH = "/root/data/input_video.mp4"


def ffprobe_duration(video_path):
    """Get video duration in seconds via ffprobe."""
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(proc.stdout.strip())


def read_analysis():
    """Load the content analysis JSON."""
    with open(ANALYSIS_PATH) as fh:
        return json.load(fh)


# =============================================================================
# 1. Output files exist and are well-formed
# =============================================================================

def test_analysis_file_valid():
    """Both output files must exist; the JSON must parse and the video must be playable."""
    assert os.path.exists(ANALYSIS_PATH), f"{ANALYSIS_PATH} missing"
    assert os.path.getsize(ANALYSIS_PATH) > 0, f"{ANALYSIS_PATH} is empty"

    report = read_analysis()
    assert isinstance(report, dict), "Analysis must be a JSON object"

    # Check all required top-level keys
    for key in ("source_length_sec", "trimmed_length_sec", "cut_total_sec",
                "cut_ratio_pct", "non_content_intervals"):
        assert key in report, f"Missing key: {key}"

    # Intervals must have correct sub-keys
    intervals = report["non_content_intervals"]
    assert isinstance(intervals, list) and len(intervals) > 0, \
        "non_content_intervals must be a non-empty list"
    for iv in intervals:
        for field in ("from", "to", "length"):
            assert field in iv, f"Interval missing '{field}': {iv}"

    # Trimmed video must be playable
    assert os.path.exists(TRIMMED_VIDEO_PATH), f"{TRIMMED_VIDEO_PATH} missing"
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", TRIMMED_VIDEO_PATH],
        capture_output=True,
    )
    assert probe.returncode == 0, "Trimmed video is not playable"


# =============================================================================
# 2. Source duration matches actual input
# =============================================================================

def test_source_duration_matches_input():
    """The reported source_length_sec must be within 2 s of the real input duration."""
    actual = ffprobe_duration(INPUT_VIDEO_PATH)
    reported = read_analysis()["source_length_sec"]
    assert abs(actual - reported) < 2.0, \
        f"Reported source duration {reported}s differs from actual {actual:.1f}s by more than 2s"


# =============================================================================
# 3. Intervals are ordered, non-overlapping, and reasonable in count
# =============================================================================

def test_intervals_ordered_and_nonoverlapping():
    """Non-content intervals must be sorted by start time and must not overlap."""
    report = read_analysis()
    intervals = report["non_content_intervals"]

    prev_end = -1.0
    for iv in intervals:
        assert iv["from"] >= 0, f"Interval starts before 0: {iv}"
        assert iv["to"] > iv["from"], f"Interval end <= start: {iv}"
        assert iv["length"] > 0, f"Interval has non-positive length: {iv}"
        assert abs(iv["length"] - (iv["to"] - iv["from"])) < 1.0, \
            f"Interval length doesn't match to-from: {iv}"
        assert iv["from"] >= prev_end - 0.5, \
            f"Intervals overlap or out of order: interval starting at {iv['from']} but previous ended at {prev_end}"
        prev_end = iv["to"]

    # There should be at least 3 non-content intervals (intro + some pauses)
    assert len(intervals) >= 3, \
        f"Expected at least 3 non-content intervals, got {len(intervals)}"


# =============================================================================
# 4. Trimmed video duration is in the expected range
# =============================================================================

def test_trimmed_video_duration_range():
    """The trimmed video should be between 280 and 420 seconds (ground truth ~346s, ±20%)."""
    actual_trimmed = ffprobe_duration(TRIMMED_VIDEO_PATH)
    report = read_analysis()

    # Verify report's trimmed_length_sec roughly matches actual video
    assert abs(actual_trimmed - report["trimmed_length_sec"]) < 2.0, \
        f"Reported trimmed duration {report['trimmed_length_sec']}s != actual {actual_trimmed:.1f}s"

    # Expected trimmed duration based on ground truth is ~346s
    lower, upper = 280.0, 420.0
    assert lower <= actual_trimmed <= upper, \
        f"Trimmed video duration {actual_trimmed:.1f}s outside expected range [{lower}, {upper}]"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
