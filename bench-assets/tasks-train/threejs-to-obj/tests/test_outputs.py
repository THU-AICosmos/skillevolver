"""
Tests for Three.js to OBJ export task.
Verifies that the exported OBJ file is valid and matches ground truth.
"""

import os
import numpy as np
import pytest


def extract_vertices(obj_path):
    """Read an OBJ file and return vertex positions as an array."""
    verts = []
    with open(obj_path, "r") as fh:
        for line in fh:
            if line.startswith("v "):
                tokens = line.strip().split()
                verts.append([float(tokens[1]), float(tokens[2]), float(tokens[3])])
    return np.array(verts)


def compute_chamfer(set_a, set_b):
    """
    Chamfer Distance between two point clouds.

    CD = mean(min‖a−b‖ for a∈A) + mean(min‖b−a‖ for b∈B)
    """
    fwd = []
    for pt in set_a:
        dists = np.linalg.norm(set_b - pt, axis=1)
        fwd.append(np.min(dists))

    bwd = []
    for pt in set_b:
        dists = np.linalg.norm(set_a - pt, axis=1)
        bwd.append(np.min(dists))

    return np.mean(fwd) + np.mean(bwd)


class TestSceneExport:
    """Test suite for OBJ export of the desk lamp scene."""

    OUTPUT_PATH = "/root/output/scene.obj"
    REFERENCE_PATH = "/root/ground_truth/scene.obj"
    MAX_CHAMFER = 1e-5

    def test_file_created(self):
        """Verify the output OBJ file exists and is non-empty."""
        assert os.path.exists(self.OUTPUT_PATH), f"Missing output: {self.OUTPUT_PATH}"
        assert os.path.getsize(self.OUTPUT_PATH) > 0, "Output OBJ is empty"

    def test_contains_geometry(self):
        """Verify the OBJ has both vertices and faces."""
        with open(self.OUTPUT_PATH, "r") as fh:
            text = fh.read()

        lines = text.strip().split("\n")
        n_verts = sum(1 for l in lines if l.startswith("v "))
        n_faces = sum(1 for l in lines if l.startswith("f "))

        assert n_verts > 0, "No vertices found in OBJ"
        assert n_faces > 0, "No faces found in OBJ"

    def test_chamfer_vs_reference(self):
        """Check geometry accuracy via Chamfer Distance against reference."""
        assert os.path.exists(self.REFERENCE_PATH), (
            f"Reference file missing: {self.REFERENCE_PATH}"
        )

        out_verts = extract_vertices(self.OUTPUT_PATH)
        ref_verts = extract_vertices(self.REFERENCE_PATH)

        assert len(out_verts) > 0, "Output has zero vertices"
        assert len(ref_verts) > 0, "Reference has zero vertices"

        cd = compute_chamfer(out_verts, ref_verts)

        assert cd < self.MAX_CHAMFER, (
            f"Chamfer Distance {cd:.8f} exceeds limit {self.MAX_CHAMFER}. "
            f"Output verts: {len(out_verts)}, Reference verts: {len(ref_verts)}"
        )
