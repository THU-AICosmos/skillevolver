"""Tests for camera motion classification and moving object segmentation."""

import json
import numpy as np
import pytest
from pathlib import Path
from scipy.ndimage import binary_dilation

WORK_DIR = Path("/root")

ALLOWED_MOTION_TYPES = {
    "Stay", "Dolly In", "Dolly Out",
    "Pan Left", "Pan Right",
    "Tilt Up", "Tilt Down",
    "Roll Left", "Roll Right"
}


def read_motion_json(fpath: Path) -> dict:
    with open(fpath) as fh:
        return json.load(fh)


def reconstruct_masks(fpath: Path):
    """Reconstruct dense boolean masks from CSR-encoded .npz archive."""
    archive = np.load(fpath)
    dims = tuple(archive['shape'].astype(int))

    result = []
    idx = 0
    while f'f_{idx}_data' in archive:
        col_indices = archive[f'f_{idx}_indices']
        row_ptrs = archive[f'f_{idx}_indptr']

        m = np.zeros(dims, dtype=bool)
        for r in range(len(row_ptrs) - 1):
            s, e = row_ptrs[r], row_ptrs[r + 1]
            m[r, col_indices[s:e]] = True
        result.append(m)
        idx += 1

    return dims, result


class TestRequiredFiles:
    """Verify the expected deliverables are present."""

    def test_camera_motion_json_exists(self):
        assert (WORK_DIR / "camera_motion.json").exists(), "Missing /root/camera_motion.json"

    def test_moving_objects_npz_exists(self):
        assert (WORK_DIR / "moving_objects.npz").exists(), "Missing /root/moving_objects.npz"


class TestMotionJsonSchema:
    """Validate structure of the camera motion predictions."""

    @pytest.fixture
    def predictions(self):
        return read_motion_json(WORK_DIR / "camera_motion.json")

    def test_root_is_mapping(self, predictions):
        assert isinstance(predictions, dict)

    def test_all_labels_recognized(self, predictions):
        for interval_labels in predictions.values():
            assert isinstance(interval_labels, list)
            for lbl in interval_labels:
                assert lbl in ALLOWED_MOTION_TYPES, f"Unknown label: {lbl}"


class TestMotionWeightedAccuracy:
    """Evaluate camera motion via per-frame weighted accuracy."""

    @pytest.fixture
    def pred_motion(self):
        return read_motion_json(WORK_DIR / "camera_motion.json")

    @pytest.fixture
    def gt_motion(self):
        return read_motion_json(WORK_DIR / "instructions.json")

    def test_weighted_frame_accuracy(self, pred_motion, gt_motion):
        """
        For each frame, compute Jaccard similarity between predicted
        and ground-truth label sets, then average across all frames.
        Threshold: >= 0.40
        """
        def unpack_frames(mapping):
            out = {}
            for key, labels in mapping.items():
                a, b = map(int, key.split("->"))
                for f in range(a, b):
                    out[f] = set(labels)
            return out

        pf = unpack_frames(pred_motion)
        gf = unpack_frames(gt_motion)
        all_f = sorted(set(pf) | set(gf))

        jaccard_scores = []
        for f in all_f:
            ps = pf.get(f, set())
            gs = gf.get(f, set())
            if len(ps | gs) == 0:
                jaccard_scores.append(1.0)
            else:
                jaccard_scores.append(len(ps & gs) / len(ps | gs))

        weighted_acc = np.mean(jaccard_scores) if jaccard_scores else 0
        print(f"\n[MOTION] Weighted frame accuracy (Jaccard): {weighted_acc:.4f}")
        assert weighted_acc >= 0.40, f"Weighted accuracy {weighted_acc:.4f} below 0.40"


class TestMaskBoundaryQuality:
    """Assess segmentation quality through boundary precision."""

    @pytest.fixture
    def pred(self):
        return reconstruct_masks(WORK_DIR / "moving_objects.npz")

    @pytest.fixture
    def gt(self):
        return reconstruct_masks(WORK_DIR / "dyn_masks.npz")

    def _boundary_iou(self, m1, m2, px=3):
        def border(m):
            return binary_dilation(m, iterations=px) & ~m
        b1, b2 = border(m1), border(m2)
        intersection = np.logical_and(b1, b2).sum()
        union = np.logical_or(b1, b2).sum()
        return intersection / union if union > 0 else 1.0

    def test_mean_boundary_iou(self, pred, gt):
        """
        Average boundary IoU (dilation=3px) across frames must be >= 0.05.
        """
        _, p_masks = pred
        _, g_masks = gt
        n = min(len(p_masks), len(g_masks))

        bious = [self._boundary_iou(p_masks[i], g_masks[i]) for i in range(n)]
        mean_biou = np.mean(bious) if bious else 0
        print(f"\n[MASK] Mean boundary IoU (3px): {mean_biou:.4f}")
        assert mean_biou >= 0.005, f"Boundary IoU {mean_biou:.4f} is below 0.005"

    def test_temporal_consistency(self, pred, gt):
        """
        Average pixel flip rate between consecutive predicted frames
        must stay below 0.15 (15% of pixels changing per step).
        """
        _, p_masks = pred
        n = len(p_masks)
        if n < 2:
            return

        flip_rates = []
        for i in range(1, n):
            flip_rates.append(np.logical_xor(p_masks[i], p_masks[i - 1]).mean())

        avg_flip = np.mean(flip_rates)
        print(f"\n[MASK] Avg temporal flip rate: {avg_flip:.6f}")
        assert avg_flip < 0.15, f"Temporal flip rate {avg_flip:.6f} exceeds 0.15"
