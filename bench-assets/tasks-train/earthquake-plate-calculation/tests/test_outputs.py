"""
Test for volcanic eruption plate analysis task.

Verifies the agent computed the correct information for the 2023 volcanic
eruption within the Australian plate that is furthest from the AU plate boundary.
"""

import json
import os
import unittest


class TestVolcanicEruptionTask(unittest.TestCase):
    """Test suite for the volcanic eruption plate analysis task."""

    # Expected values from the reference solution
    # Location: Great Victoria Basin anomaly on 2023-02-06
    EXPECTED = {
        "event_id": "ve20230002",
        "location": "Great Victoria Basin anomaly",
        "timestamp": "2023-02-06T14:38:39Z",
        "vei": 5.68,
        "lat": -30.0,
        "lon": 128.5,
        "boundary_distance_km": 2086.56,
    }

    # Tolerances
    DIST_TOL = 0.01  # +/- 0.01 km
    COORD_TOL = 0.0001  # +/- 0.0001 degrees
    VEI_TOL = 0.01  # +/- 0.01

    loaded = None

    @classmethod
    def setUpClass(cls):
        """Load the result file once for all tests."""
        candidates = ["/root/result.json", "result.json"]
        filepath = None
        for c in candidates:
            if os.path.exists(c):
                filepath = c
                break

        if filepath is None:
            raise FileNotFoundError("Result file not found. Expected /root/result.json")

        with open(filepath, encoding="utf-8") as fh:
            cls.loaded = json.load(fh)

    def test_result_structure(self):
        """Verify result file exists, is valid JSON, and has all required fields."""
        needed = [
            "event_id",
            "location",
            "timestamp",
            "vei",
            "lat",
            "lon",
            "boundary_distance_km",
        ]
        for key in needed:
            self.assertIn(key, self.loaded, f"Missing required field: {key}")

    def test_event_id_matches(self):
        """
        Verify volcanic event ID is correct.

        This is the most critical test - confirms the correct eruption
        was identified (furthest from AU plate boundary within AU plate).
        """
        want = self.EXPECTED["event_id"]
        got = self.loaded.get("event_id")
        self.assertEqual(
            got,
            want,
            f"Expected event_id '{want}', got '{got}' - wrong eruption selected!",
        )

    def test_location_matches(self):
        """Verify eruption location description is correct."""
        want = self.EXPECTED["location"]
        got = self.loaded.get("location")
        self.assertEqual(got, want, f"Expected location '{want}', got '{got}'")

    def test_timestamp_matches(self):
        """Verify eruption timestamp is correct."""
        want = self.EXPECTED["timestamp"]
        got = self.loaded.get("timestamp")
        self.assertEqual(got, want, f"Expected timestamp '{want}', got '{got}'")

    def test_vei_within_tolerance(self):
        """Verify eruption magnitude (VEI) is within tolerance (+/-0.01)."""
        val = self.loaded.get("vei")
        self.assertIsInstance(val, (int, float), "VEI should be a number")
        self.assertAlmostEqual(
            val,
            self.EXPECTED["vei"],
            delta=self.VEI_TOL,
            msg=f"Expected VEI {self.EXPECTED['vei']} +/- {self.VEI_TOL}, got {val}",
        )

    def test_latitude_within_tolerance(self):
        """Verify event latitude is within tolerance (+/-0.0001 degrees)."""
        val = self.loaded.get("lat")
        self.assertIsInstance(val, (int, float), "Latitude should be a number")
        self.assertAlmostEqual(
            val,
            self.EXPECTED["lat"],
            delta=self.COORD_TOL,
            msg=f"Expected lat {self.EXPECTED['lat']} +/- {self.COORD_TOL}, got {val}",
        )

    def test_longitude_within_tolerance(self):
        """Verify event longitude is within tolerance (+/-0.0001 degrees)."""
        val = self.loaded.get("lon")
        self.assertIsInstance(val, (int, float), "Longitude should be a number")
        self.assertAlmostEqual(
            val,
            self.EXPECTED["lon"],
            delta=self.COORD_TOL,
            msg=f"Expected lon {self.EXPECTED['lon']} +/- {self.COORD_TOL}, got {val}",
        )

    def test_boundary_distance_within_tolerance(self):
        """
        Verify computed boundary distance is within tolerance (+/-0.01 km).

        The distance represents the furthest volcanic eruption within the
        Australian plate from the AU plate boundary in 2023.
        """
        val = self.loaded.get("boundary_distance_km")
        self.assertIsInstance(val, (int, float), "Distance should be a number")

        self.assertGreater(val, 0.0, msg="Distance should be positive")
        self.assertLess(
            val, 10000.0, msg="Distance seems unreasonably large (> 10000 km)"
        )

        self.assertAlmostEqual(
            val,
            self.EXPECTED["boundary_distance_km"],
            delta=self.DIST_TOL,
            msg=(
                f"Expected {self.EXPECTED['boundary_distance_km']} +/- {self.DIST_TOL} km, "
                f"got {val} km"
            ),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
