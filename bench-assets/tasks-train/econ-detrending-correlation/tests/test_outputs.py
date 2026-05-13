"""
Test for econ_detrending_correlation training variant.

Verifies the agent computed the correct correlation coefficient between
detrended (HP-filtered) real Government Spending and
real Exports for 1965-2019.
"""

import os
import unittest


class TestMacroCorrelation(unittest.TestCase):
    """Test suite for the government-exports detrending correlation task."""

    # Expected correlation from the reference solution
    # Computed using HP filter (λ=100) on log-real values
    EXPECTED_CORRELATION = 0.85420

    # Tolerance: ±0.001 to account for minor differences
    TOLERANCE = 0.001

    def get_result_path(self):
        """Find the result file in expected locations."""
        paths = ["/root/result.txt", "result.txt"]
        for path in paths:
            if os.path.exists(path):
                return path
        return None

    def test_result_file_exists(self):
        """Verify result file was created."""
        path = self.get_result_path()
        self.assertIsNotNone(path, "Result file not found. Expected /root/result.txt")

    def test_result_is_valid_number(self):
        """Verify result file contains a valid floating point number."""
        path = self.get_result_path()
        if path is None:
            self.skipTest("Result file not found")

        with open(path) as f:
            content = f.read().strip()

        try:
            float(content)
        except ValueError:
            self.fail(f"Result '{content}' is not a valid number")

    def test_correlation_value_correct(self):
        """
        Verify the computed correlation matches the expected value.

        The correlation should be approximately 0.854, indicating that
        government spending and exports are strongly procyclical and move
        together over the business cycle.
        """
        path = self.get_result_path()
        if path is None:
            self.skipTest("Result file not found")

        with open(path) as f:
            content = f.read().strip()

        try:
            computed = float(content)
        except ValueError:
            self.fail(f"Result '{content}' is not a valid number")

        print(f"Agent's result: {content}")
        print(f"Expected: {self.EXPECTED_CORRELATION}")
        print(f"Tolerance: ±{self.TOLERANCE}")

        self.assertAlmostEqual(
            computed,
            self.EXPECTED_CORRELATION,
            delta=self.TOLERANCE,
            msg=(f"Correlation mismatch. "
                 f"Expected {self.EXPECTED_CORRELATION} ± {self.TOLERANCE}, "
                 f"got {computed}"),
        )

    def test_result_format(self):
        """Verify result is formatted with appropriate decimal places."""
        path = self.get_result_path()
        if path is None:
            self.skipTest("Result file not found")

        with open(path) as f:
            content = f.read().strip()

        # Should be a decimal number, not scientific notation
        self.assertNotIn("e", content.lower(), "Result should not be in scientific notation")

        # Should have decimal places (not an integer)
        self.assertIn(".", content, "Result should include decimal places")


if __name__ == "__main__":
    unittest.main(verbosity=2)
