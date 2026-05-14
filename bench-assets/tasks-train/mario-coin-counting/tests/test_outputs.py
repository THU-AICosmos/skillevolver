import glob
import os

EXPECTED_CSV = "/tests/expected_output.csv"
RESULT_CSV = "/root/detection_summary.csv"


class TestKeyframeExtraction:
    def test_frames_were_extracted(self):
        """Verify that keyframe PNGs exist in /root."""
        frames = glob.glob("/root/frame_*.png")
        assert len(frames) > 0, "No keyframes found"

    def test_frames_are_grayscale(self):
        """Ensure all extracted frames are single-channel (grayscale)."""
        import cv2

        for path in sorted(glob.glob("/root/frame_*.png")):
            img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            assert img is not None, f"Could not read {path}"
            assert len(img.shape) == 2, f"{path} is not grayscale"


class TestDetectionSummary:
    def test_csv_columns_and_row_count(self):
        """Check that the output CSV has the right shape and headers."""
        import pandas as pd

        expected = pd.read_csv(EXPECTED_CSV)
        assert os.path.isfile(RESULT_CSV), f"{RESULT_CSV} not found"
        result = pd.read_csv(RESULT_CSV)

        assert list(result.columns) == ["frame", "gold_coins", "shell_creatures"]
        assert len(result) == len(expected), "Row count mismatch"

    def test_gold_coin_counts_match(self):
        """Verify per-frame gold coin counts match ground truth."""
        import pandas as pd

        expected = pd.read_csv(EXPECTED_CSV)
        result = pd.read_csv(RESULT_CSV)
        assert expected["gold_coins"].equals(result["gold_coins"])

    def test_shell_creature_counts_match(self):
        """Verify per-frame shell creature (turtle) counts match ground truth."""
        import pandas as pd

        expected = pd.read_csv(EXPECTED_CSV)
        result = pd.read_csv(RESULT_CSV)
        assert expected["shell_creatures"].equals(result["shell_creatures"])
