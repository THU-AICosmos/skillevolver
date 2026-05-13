import json
import os
import shutil


def copy_artifacts():
    """Copy output files to /logs/verifier/ for trajectory inspection."""
    os.makedirs("/logs/verifier", exist_ok=True)
    for name in ("detected_fillers.json", "filler_report.txt"):
        src = f"/root/{name}"
        if os.path.exists(src):
            shutil.copy(src, f"/logs/verifier/{name}")


def load_detections():
    with open("/root/detected_fillers.json") as f:
        return json.load(f)


class TestSpeechCoachOutputs:
    """Reduced test suite for the speech-coaching filler detection variant."""

    def test_detections_file_format(self):
        """Verify detected_fillers.json exists and every entry has the
        required fields with correct types (phrase=str, start_time=number)."""
        assert os.path.exists("/root/detected_fillers.json"), (
            "/root/detected_fillers.json not found"
        )
        detections = load_detections()
        assert isinstance(detections, list), "Top-level value must be a JSON array"
        assert len(detections) > 0, "Detections array must not be empty"

        for entry in detections:
            assert "phrase" in entry, "Each entry must contain a 'phrase' key"
            assert isinstance(entry["phrase"], str), "'phrase' must be a string"
            assert "start_time" in entry, "Each entry must contain a 'start_time' key"
            assert isinstance(entry["start_time"], (int, float)), (
                "'start_time' must be a number"
            )

    def test_detection_count_and_diversity(self):
        """Check that the total number of detections and the variety of
        filler types are within a plausible range for the input video."""
        detections = load_detections()
        total = len(detections)

        # The ground-truth has ~127 fillers; allow broad but bounded range
        assert 60 <= total <= 200, (
            f"Expected between 60 and 200 detected fillers, got {total}"
        )

        distinct_phrases = {e["phrase"].lower().strip() for e in detections}
        assert len(distinct_phrases) >= 5, (
            f"Expected at least 5 distinct filler phrase types, found "
            f"{len(distinct_phrases)}: {distinct_phrases}"
        )

    def test_summary_report_exists(self):
        """Verify that filler_report.txt was created and is non-empty."""
        path = "/root/filler_report.txt"
        assert os.path.exists(path), f"{path} not found"
        content = open(path).read()
        assert len(content.strip()) > 0, "filler_report.txt is empty"

    def test_z_copy_artifacts(self):
        """Copy outputs to /logs/verifier/ for inspection."""
        copy_artifacts()
