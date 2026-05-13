"""
Test suite for video dead air trimmer task.

Reduced test set focusing on:
  1. Output validity (trimmed video exists and is playable, edit log is well-formed)
  2. Segment detection precision against ground truth
  3. Trimmed video duration within expected range
  4. Audio-to-edit-log correspondence via waveform correlation
"""

import json
import os
import subprocess
import tempfile

import numpy as np
import pytest
from scipy.io import wavfile

GROUND_TRUTH_FILE = "/tests/ground_truth.json"
EDIT_LOG_FILE = "edit_log.json"
TRIMMED_VIDEO_FILE = "trimmed_lecture.mp4"


def probe_duration(path):
    """Return duration in seconds of a media file via ffprobe."""
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(proc.stdout.strip())


def read_ground_truth():
    with open(GROUND_TRUTH_FILE) as fh:
        return json.load(fh)


def read_edit_log():
    with open(EDIT_LOG_FILE) as fh:
        return json.load(fh)


def _iou(a, b):
    """Intersection-over-union for two time spans given as dicts with start/end or from_sec/to_sec."""
    a_start = a.get("start", a.get("from_sec"))
    a_end = a.get("end", a.get("to_sec"))
    b_start = b.get("start", b.get("from_sec"))
    b_end = b.get("end", b.get("to_sec"))
    overlap = max(0, min(a_end, b_end) - max(a_start, b_start))
    union = (a_end - a_start) + (b_end - b_start) - overlap
    return overlap / union if union > 0 else 0


# ── Test 1: output validity ──────────────────────────────────────────────────

def test_outputs_valid():
    """Trimmed video must exist, be playable, and edit_log.json must have the right keys."""
    # Video checks
    assert os.path.isfile(TRIMMED_VIDEO_FILE), f"{TRIMMED_VIDEO_FILE} missing"
    assert os.path.getsize(TRIMMED_VIDEO_FILE) > 0, f"{TRIMMED_VIDEO_FILE} is empty"
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", TRIMMED_VIDEO_FILE],
        capture_output=True,
    )
    assert probe.returncode == 0, "Trimmed video is not a valid media file"

    # Edit log checks
    assert os.path.isfile(EDIT_LOG_FILE), f"{EDIT_LOG_FILE} missing"
    log = read_edit_log()
    for key in ("source_length_sec", "output_length_sec", "dead_air_total_sec",
                "cut_ratio_percent", "cuts"):
        assert key in log, f"edit_log.json missing key: {key}"
    assert isinstance(log["cuts"], list) and len(log["cuts"]) > 0, "cuts list must be non-empty"
    for c in log["cuts"]:
        assert "from_sec" in c and "to_sec" in c and "length_sec" in c, \
            f"Cut entry missing required fields: {c}"


# ── Test 2: segment detection precision ──────────────────────────────────────

def test_cut_precision():
    """At least 60 % of reported cuts must match a ground-truth segment (IoU > 0.3)."""
    gt = read_ground_truth()
    log = read_edit_log()

    gt_segs = gt["segments_to_remove"]
    reported_cuts = log["cuts"]

    hits = 0
    for cut in reported_cuts:
        for gt_seg in gt_segs:
            if _iou(cut, gt_seg) > 0.3:
                hits += 1
                break

    precision = hits / len(reported_cuts) if reported_cuts else 1.0
    assert precision >= 0.6, (
        f"Cut precision {precision:.0%} below 60 % "
        f"({hits}/{len(reported_cuts)} cuts matched ground truth)"
    )


# ── Test 3: trimmed video duration ──────────────────────────────────────────

def test_trimmed_duration_in_range():
    """Trimmed video duration should be within 20 % of the expected value."""
    gt = read_ground_truth()
    expected = gt["video"]["expected_compressed_duration_seconds"]
    actual = probe_duration(TRIMMED_VIDEO_FILE)

    lo = expected * 0.80
    hi = expected * 1.20
    assert lo <= actual <= hi, (
        f"Trimmed duration {actual:.1f}s outside [{lo:.0f}, {hi:.0f}]s "
        f"(expected ~{expected}s)"
    )


# ── Test 4: audio waveform correlation ──────────────────────────────────────

def test_audio_correlation():
    """Reconstruct audio from the original using the edit log's cut list,
    then check Pearson correlation with the trimmed video's actual audio (>0.95)."""
    log = read_edit_log()
    cuts = sorted(log["cuts"], key=lambda c: c["from_sec"])
    src_video = "/root/data/input_video.mp4"
    total_dur = log["source_length_sec"]

    # Build keep-intervals (complement of cuts)
    keeps = []
    pos = 0
    for c in cuts:
        if c["from_sec"] > pos:
            keeps.append((pos, c["from_sec"]))
        pos = c["to_sec"]
    if pos < total_dur:
        keeps.append((pos, total_dur))

    assert keeps, "No audio left after applying all cuts"

    with tempfile.TemporaryDirectory() as td:
        # ffmpeg filter: trim + concat the kept intervals
        parts = []
        for idx, (s, e) in enumerate(keeps):
            parts.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[k{idx}]")
        labels = "".join(f"[k{i}]" for i in range(len(keeps)))
        fc = ";".join(parts) + f";{labels}concat=n={len(keeps)}:v=0:a=1[out]"

        r1 = subprocess.run(
            ["ffmpeg", "-y", "-i", src_video, "-filter_complex", fc,
             "-map", "[out]", "-ar", "16000", "-ac", "1", f"{td}/ref.wav"],
            capture_output=True,
        )
        assert r1.returncode == 0, f"ffmpeg reconstruct failed: {r1.stderr.decode()}"

        r2 = subprocess.run(
            ["ffmpeg", "-y", "-i", TRIMMED_VIDEO_FILE, "-vn",
             "-ar", "16000", "-ac", "1", f"{td}/actual.wav"],
            capture_output=True,
        )
        assert r2.returncode == 0, f"ffmpeg extract failed: {r2.stderr.decode()}"

        _, ref_wav = wavfile.read(f"{td}/ref.wav")
        _, act_wav = wavfile.read(f"{td}/actual.wav")

        ref_f = ref_wav.astype(np.float32) / 32768.0
        act_f = act_wav.astype(np.float32) / 32768.0

        n = min(len(ref_f), len(act_f))
        corr = np.corrcoef(ref_f[:n], act_f[:n])[0, 1]

        assert corr > 0.95, (
            f"Audio correlation {corr:.3f} is below 0.95 — "
            "trimmed audio does not match the described cuts"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
