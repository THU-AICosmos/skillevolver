import json
import os
import subprocess

# The input video is ~270s with ~127 filler words
# After removing fillers (~50s worth), cleaned video should be ~190-250s
MIN_CLEANED_DURATION = 170.0
MAX_CLEANED_DURATION = 255.0

# We expect roughly 80-160 filler detections
MIN_FILLER_COUNT = 60
MAX_FILLER_COUNT = 180

VALID_FILLERS = {
    "um", "uh", "hum", "hmm", "mhm",
    "like", "yeah", "so", "well", "okay", "basically",
    "you know", "i mean", "kind of", "i guess",
}


def probe_duration(filepath):
    """Return duration of a media file in seconds via ffprobe."""
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            filepath,
        ],
        capture_output=True, text=True,
    )
    return float(proc.stdout.strip())


def read_fillers():
    with open("/root/detected_fillers.json") as fh:
        return json.load(fh)


class TestCleanedVideo:
    """Tests for the cleaned-video variant of the filler-word task."""

    def test_detected_fillers_file_exists(self):
        """The filler annotations file must be present."""
        assert os.path.exists("/root/detected_fillers.json"), \
            "/root/detected_fillers.json was not created"

    def test_detected_fillers_schema(self):
        """Each entry must contain 'filler' and 'start_time' keys."""
        entries = read_fillers()
        assert isinstance(entries, list) and len(entries) > 0, \
            "detected_fillers.json should be a non-empty JSON array"
        for entry in entries:
            assert "filler" in entry, "Missing 'filler' key in entry"
            assert "start_time" in entry, "Missing 'start_time' key in entry"
            assert isinstance(entry["start_time"], (int, float)), \
                "start_time must be numeric"

    def test_filler_count_in_range(self):
        """Number of detected fillers should be in a plausible range."""
        entries = read_fillers()
        assert len(entries) >= MIN_FILLER_COUNT, (
            f"Too few fillers detected ({len(entries)}). "
            f"Expected at least {MIN_FILLER_COUNT}."
        )
        assert len(entries) <= MAX_FILLER_COUNT, (
            f"Too many fillers detected ({len(entries)}). "
            f"Expected at most {MAX_FILLER_COUNT}."
        )

    def test_cleaned_video_duration(self):
        """Cleaned video should be shorter than input but not too short."""
        assert os.path.exists("/root/cleaned.mp4"), \
            "/root/cleaned.mp4 was not created"
        input_dur = probe_duration("/root/input.mp4")
        cleaned_dur = probe_duration("/root/cleaned.mp4")

        assert cleaned_dur < input_dur, (
            f"Cleaned video ({cleaned_dur:.1f}s) must be shorter "
            f"than the input ({input_dur:.1f}s)"
        )
        assert cleaned_dur >= MIN_CLEANED_DURATION, (
            f"Cleaned video too short ({cleaned_dur:.1f}s). "
            f"Expected >= {MIN_CLEANED_DURATION}s."
        )
        assert cleaned_dur <= MAX_CLEANED_DURATION, (
            f"Cleaned video too long ({cleaned_dur:.1f}s). "
            f"Expected <= {MAX_CLEANED_DURATION}s."
        )
