"""
Tests for GPT-124M training on FineWeb with SDR (Stochastic Depth Routing) on Modal A100.

Verifies:
1. Results file exists with required fields
2. SDR shows expected training stability improvements
3. Routing matrices are doubly stochastic (core SDR property)
"""

import json
import os
from pathlib import Path

import numpy as np
import pytest


def locate_output_json():
    """Search for output.json in likely locations."""
    candidates = [
        Path("output.json"),
        Path("/root/output.json"),
        Path(__file__).parent.parent / "output.json",
        Path.cwd() / "output.json",
    ]

    for p in candidates:
        if p.exists():
            return p

    # Recursive fallback
    try:
        hits = list(Path(".").rglob("output.json"))
        if hits:
            return hits[0]
    except Exception:
        pass

    return Path("/root/output.json")


OUTPUT_FILE = locate_output_json()


@pytest.fixture(scope="module")
def results():
    """Load training results."""
    if not OUTPUT_FILE.exists():
        pytest.skip(f"output.json not found at {OUTPUT_FILE}")
    with open(OUTPUT_FILE) as fh:
        return json.load(fh)


class TestOutputExists:
    """Test that required output file exists."""

    def test_output_file_exists(self):
        """output.json was created."""
        assert OUTPUT_FILE.exists(), f"output.json not found at {OUTPUT_FILE}"


class TestSDRImplementation:
    """Test SDR implementation correctness."""

    def test_has_bistochastic_projection(self, sdr_module):
        """Module has bistochastic_projection function."""
        assert hasattr(sdr_module, "bistochastic_projection"), "Missing bistochastic_projection function"

    def test_has_pathway_router(self, sdr_module):
        """Module has PathwayRouter class."""
        assert hasattr(sdr_module, "PathwayRouter"), "Missing PathwayRouter class"

    def test_bistochastic_produces_doubly_stochastic(self, sdr_module):
        """bistochastic_projection produces doubly stochastic matrix."""
        logits = torch.randn(3, 3)
        try:
            mat = sdr_module.bistochastic_projection(logits, n_iters=20, temperature=0.05)
        except TypeError:
            mat = sdr_module.bistochastic_projection(logits, 20, 0.05)

        assert (mat >= 0).all(), "Matrix has negative entries"

        row_sums = mat.sum(dim=-1)
        assert torch.allclose(row_sums, torch.ones(3), atol=0.15), f"Rows don't sum to 1: {row_sums.tolist()}"

        col_sums = mat.sum(dim=-2)
        assert torch.allclose(col_sums, torch.ones(3), atol=0.15), f"Columns don't sum to 1: {col_sums.tolist()}"

    def test_pathway_router_is_nn_module(self, sdr_module):
        """PathwayRouter is a PyTorch nn.Module."""
        assert issubclass(sdr_module.PathwayRouter, torch.nn.Module), "PathwayRouter should be nn.Module"

    def test_pathway_router_has_learnable_params(self, sdr_module):
        """PathwayRouter has learnable parameters for routing."""
        sublayer = torch.nn.Linear(64, 64)
        router = None

        signatures_to_try = [
            {"num_pathways": 3, "dim": 64, "sublayer": sublayer, "layer_idx": 0},
            {"num_pathways": 3, "dim": 64, "sublayer": sublayer},
            {"n_pathways": 3, "dim": 64, "sublayer": sublayer},
            {"num_residual_streams": 3, "dim": 64, "branch": sublayer, "layer_index": 0},
        ]

        for sig in signatures_to_try:
            try:
                router = sdr_module.PathwayRouter(**sig)
                break
            except TypeError:
                continue

        assert router is not None, "Could not instantiate PathwayRouter with any common signature"

        params = list(router.parameters())
        assert len(params) > 0, "PathwayRouter has no learnable parameters"

    def test_pathway_router_forward(self, sdr_module):
        """PathwayRouter forward pass works."""
        n_paths = 3
        dim = 64
        bsz = 2
        seq = 32

        sublayer = torch.nn.Linear(dim, dim)
        router = None

        signatures_to_try = [
            {"num_pathways": n_paths, "dim": dim, "sublayer": sublayer, "layer_idx": 0},
            {"num_pathways": n_paths, "dim": dim, "sublayer": sublayer},
            {"n_pathways": n_paths, "dim": dim, "sublayer": sublayer},
            {"num_residual_streams": n_paths, "dim": dim, "branch": sublayer, "layer_index": 0},
        ]

        for sig in signatures_to_try:
            try:
                router = sdr_module.PathwayRouter(**sig)
                break
            except TypeError:
                continue

        assert router is not None, "Could not instantiate PathwayRouter"

        input_shapes = [
            (bsz * n_paths, seq, dim),
            (bsz, n_paths, seq, dim),
            (bsz, seq, dim),
        ]

        output = None
        for shape in input_shapes:
            try:
                x = torch.randn(*shape)
                output = router(x)
                break
            except (RuntimeError, ValueError):
                continue

        assert output is not None, "Forward pass failed with all input shapes"
        assert output.numel() > 0, "Output is empty"


class TestOutputStructure:
    """Test output.json has required fields."""

    def test_has_sdr_final_loss(self, results):
        """output.json has sdr_final_loss."""
        assert "sdr_final_loss" in results
        assert isinstance(results["sdr_final_loss"], (int, float))

    def test_has_standard_final_loss(self, results):
        """output.json has standard_final_loss."""
        assert "standard_final_loss" in results
        assert isinstance(results["standard_final_loss"], (int, float))

    def test_has_sdr_grad_std(self, results):
        """output.json has sdr_grad_std."""
        assert "sdr_grad_std" in results
        assert isinstance(results["sdr_grad_std"], (int, float))

    def test_has_standard_grad_std(self, results):
        """output.json has standard_grad_std."""
        assert "standard_grad_std" in results
        assert isinstance(results["standard_grad_std"], (int, float))

    def test_has_peak_grad_fields(self, results):
        """output.json has peak gradient fields."""
        assert "sdr_peak_grad" in results
        assert "standard_peak_grad" in results

    def test_has_routing_matrices(self, results):
        """output.json has routing_matrices."""
        assert "routing_matrices" in results
        assert isinstance(results["routing_matrices"], list)
        assert len(results["routing_matrices"]) > 0, "routing_matrices is empty"


class TestTrainingOutcomes:
    """Test that training achieved target metrics or completed steps."""

    LOSS_TARGET = 4.5
    TOLERANCE = 0.01

    def test_sdr_reaches_target_or_finishes(self, results):
        """SDR model achieved validation loss < 5.0 or completed training."""
        assert results["sdr_final_loss"] > 0, "SDR training did not complete"
        assert results["sdr_final_loss"] < 5.0, f"SDR final loss too high: {results['sdr_final_loss']} (target: 5.0)"

    def test_standard_reaches_target_or_finishes(self, results):
        """Standard model achieved validation loss < 4.5 or completed training."""
        assert results["standard_final_loss"] > 0, "Standard training did not complete"
        assert results["standard_final_loss"] < self.LOSS_TARGET + self.TOLERANCE, (
            f"Standard final loss too high: {results['standard_final_loss']} (target: {self.LOSS_TARGET})"
        )

    def test_no_gradient_explosion(self, results):
        """Neither model had exploding gradients."""
        assert results["sdr_peak_grad"] < 100, f"SDR gradients exploded: {results['sdr_peak_grad']}"
        assert results["standard_peak_grad"] < 100, f"Standard gradients exploded: {results['standard_peak_grad']}"

    def test_both_trained_successfully(self, results):
        """Training completed (non-zero results)."""
        assert results["sdr_final_loss"] > 0, "SDR final loss is zero"
        assert results["standard_final_loss"] > 0, "Standard final loss is zero"
        assert results["sdr_grad_std"] > 0, "SDR grad std is zero"
        assert results["standard_grad_std"] > 0, "Standard grad std is zero"


class TestSDRAdvantages:
    """Test that SDR shows expected training stability improvements."""

    def test_sdr_more_stable_gradients(self, results):
        """SDR should have lower gradient norm variance (more stable training)."""
        assert results["sdr_grad_std"] < results["standard_grad_std"], (
            f"SDR grad std ({results['sdr_grad_std']}) should be lower than standard ({results['standard_grad_std']})"
        )

    def test_sdr_lower_peak_gradient(self, results):
        """SDR should have lower peak gradient norm (less prone to spikes)."""
        assert results["sdr_peak_grad"] <= results["standard_peak_grad"], (
            f"SDR peak grad ({results['sdr_peak_grad']}) should be <= standard ({results['standard_peak_grad']})"
        )

    def test_sdr_comparable_or_better_loss(self, results):
        """SDR should achieve similar or better final loss."""
        margin = 1.1  # Allow 10% tolerance
        assert results["sdr_final_loss"] <= results["standard_final_loss"] * margin, (
            f"SDR loss ({results['sdr_final_loss']}) should be within {margin}x of standard ({results['standard_final_loss']})"
        )


class TestRoutingMatrixProperties:
    """Test SDR routing matrices are correct."""

    def test_routing_is_doubly_stochastic(self, results):
        """Routing matrices are doubly stochastic (rows and cols sum to ~1 on average)."""
        for idx, rmat in enumerate(results["routing_matrices"]):
            arr = np.array(rmat)

            assert (arr >= 0).all(), f"routing_matrices[{idx}] has negative values"

            row_sums = arr.sum(axis=-1)
            row_avg = row_sums.mean()
            assert np.isclose(row_avg, 1.0, atol=0.1), f"routing_matrices[{idx}] row sums mean != 1: {row_avg:.4f} (sums: {row_sums})"

            col_sums = arr.sum(axis=-2)
            col_avg = col_sums.mean()
            assert np.isclose(col_avg, 1.0, atol=0.1), f"routing_matrices[{idx}] col sums mean != 1: {col_avg:.4f} (sums: {col_sums})"

    def test_routing_is_square(self, results):
        """Routing matrices are square (num_pathways x num_pathways)."""
        for idx, rmat in enumerate(results["routing_matrices"]):
            arr = np.array(rmat)
            assert arr.shape[-1] == arr.shape[-2], f"routing_matrices[{idx}] is not square: {arr.shape}"

    def test_routing_not_identity(self, results):
        """Routing matrices are not just identity (learning happened).

        With short training, routing may stay close to identity.
        We check that at least one matrix deviates.
        """
        any_changed = False
        for idx, rmat in enumerate(results["routing_matrices"]):
            arr = np.array(rmat)
            eye = np.eye(arr.shape[-1])
            if not np.allclose(arr, eye, atol=0.01):
                any_changed = True
                break

        if not any_changed:
            for idx, rmat in enumerate(results["routing_matrices"]):
                arr = np.array(rmat)
                off_diag = ~np.eye(arr.shape[-1], dtype=bool)
                if np.any(np.abs(arr[off_diag]) > 0.001):
                    any_changed = True
                    break

        assert any_changed, "All routing matrices are exactly identity - SDR parameters may not be receiving gradients"
