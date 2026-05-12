import glob
import os

GROUND_TRUTH = "/tests/expected_output.csv"
OUTPUT_FILE = "/root/replay_analysis.csv"


class TestReplayAnalysis:
    def test_key_frames_extracted(self):
        """Check that keyframes have been extracted from the video."""
        keyframes = len(glob.glob("/root/keyframes_*.png"))
        assert keyframes > 0

    def test_grayscale_conversion(self):
        """Check that all keyframes have been converted to grayscale."""
        import cv2

        for frame in glob.glob("/root/keyframes_*.png"):
            img = cv2.imread(frame, cv2.IMREAD_UNCHANGED)
            assert len(img.shape) == 2, f"{frame} is not grayscale"

    def test_replay_csv_structure(self):
        """Check that the output CSV has the correct columns and row count."""
        import pandas as pd

        df_gt = pd.read_csv(GROUND_TRUTH)
        assert os.path.isfile(OUTPUT_FILE), f"{OUTPUT_FILE} does not exist"
        df_out = pd.read_csv(OUTPUT_FILE)

        assert len(df_gt) == len(df_out), "Number of keyframes does not match"
        assert list(df_out.columns) == ["frame_id", "coins", "turtles"]

    def test_coin_counts(self):
        """Check that coin counts match ground truth."""
        import pandas as pd

        df_gt = pd.read_csv(GROUND_TRUTH)
        df_out = pd.read_csv(OUTPUT_FILE)
        assert df_gt["coins"].equals(df_out["coins"])

    def test_turtle_counts(self):
        """Check that turtle counts match ground truth."""
        import pandas as pd

        df_gt = pd.read_csv(GROUND_TRUTH)
        df_out = pd.read_csv(OUTPUT_FILE)
        assert df_gt["turtles"].equals(df_out["turtles"])
