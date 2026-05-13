"""
Tests for the coral reef fish school clustering task.
Compares agent's Pareto frontier against expected ground truth.
"""

from pathlib import Path

import pandas as pd
import pytest


class TestParetoFrontier:
    """Test suite for Pareto frontier output."""

    RESULT_PATH = Path("/root/optimal_tradeoffs.csv")
    EXPECTED_PATH = Path(__file__).parent / "expected_frontier.csv"

    SCORE_TOL = 0.0001
    OFFSET_TOL = 0.001

    @pytest.fixture
    def agent_frontier(self):
        """Load agent's Pareto frontier."""
        assert self.RESULT_PATH.exists(), f"Result file not found: {self.RESULT_PATH}"
        return pd.read_csv(self.RESULT_PATH)

    @pytest.fixture
    def expected_frontier(self):
        """Load expected Pareto frontier."""
        return pd.read_csv(self.EXPECTED_PATH)

    def test_result_file_exists(self):
        """Test that the result file exists."""
        assert self.RESULT_PATH.exists(), f"Result file not found at {self.RESULT_PATH}"

    def test_result_file_not_empty(self, agent_frontier):
        """Test that the result file is not empty."""
        assert len(agent_frontier) > 0, "Result file is empty"

    def test_required_columns(self, agent_frontier):
        """Test that all required columns are present."""
        required = ["score", "offset", "min_pts", "eps_radius", "stretch_factor"]
        missing = [col for col in required if col not in agent_frontier.columns]
        assert len(missing) == 0, f"Missing columns: {missing}"

    def test_score_values_valid(self, agent_frontier):
        """Test that score values are in valid range [0, 1]."""
        assert (agent_frontier["score"] >= 0).all(), "Score values must be >= 0"
        assert (agent_frontier["score"] <= 1).all(), "Score values must be <= 1"

    def test_offset_values_positive(self, agent_frontier):
        """Test that offset values are positive."""
        assert (agent_frontier["offset"] > 0).all(), "Offset values must be positive"

    def test_hyperparameter_ranges(self, agent_frontier):
        """Test that hyperparameters are within valid ranges."""
        assert (agent_frontier["min_pts"] >= 2).all(), "min_pts must be >= 2"
        assert (agent_frontier["min_pts"] <= 7).all(), "min_pts must be <= 7"
        assert (agent_frontier["eps_radius"] >= 5).all(), "eps_radius must be >= 5"
        assert (agent_frontier["eps_radius"] <= 35).all(), "eps_radius must be <= 35"
        assert (agent_frontier["stretch_factor"] >= 0.55).all(), "stretch_factor must be >= 0.55"
        assert (agent_frontier["stretch_factor"] <= 1.65).all(), "stretch_factor must be <= 1.65"

    def test_is_valid_pareto_frontier(self, agent_frontier):
        """Test that no point in the frontier dominates another."""
        frontier = agent_frontier[["score", "offset"]].values

        for i, point in enumerate(frontier):
            for j, other in enumerate(frontier):
                if i == j:
                    continue
                # Check if 'other' dominates 'point'
                # (higher score AND lower offset)
                if other[0] >= point[0] and other[1] <= point[1]:
                    if other[0] > point[0] or other[1] < point[1]:
                        pytest.fail(
                            f"Point {i} (score={point[0]:.4f}, offset={point[1]:.2f}) "
                            f"is dominated by point {j} (score={other[0]:.4f}, offset={other[1]:.2f})"
                        )

    def test_all_expected_points_found(self, agent_frontier, expected_frontier):
        """Test that every expected Pareto point is found in agent's output."""
        missing_points = []

        for _idx, expected_row in expected_frontier.iterrows():
            found = False
            for _, agent_row in agent_frontier.iterrows():
                params_match = (
                    int(agent_row["min_pts"]) == int(expected_row["min_pts"])
                    and int(agent_row["eps_radius"]) == int(expected_row["eps_radius"])
                    and abs(agent_row["stretch_factor"] - expected_row["stretch_factor"]) < 0.01
                )
                score_match = abs(agent_row["score"] - expected_row["score"]) <= self.SCORE_TOL
                offset_match = abs(agent_row["offset"] - expected_row["offset"]) <= self.OFFSET_TOL

                if params_match and score_match and offset_match:
                    found = True
                    break

            if not found:
                missing_points.append(
                    f"score={expected_row['score']:.4f}, offset={expected_row['offset']:.2f}, "
                    f"params=({expected_row['min_pts']}, {expected_row['eps_radius']}, {expected_row['stretch_factor']})"
                )

        assert len(missing_points) == 0, f"Missing {len(missing_points)} expected Pareto points:\n" + "\n".join(missing_points)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
