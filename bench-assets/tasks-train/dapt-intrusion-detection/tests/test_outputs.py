"""
Tests for network capacity planning audit task.

Verifies that the network analysis produces correct measurements for:
- Bandwidth & Payload: total bytes, avg/max packet size
- Protocol Breakdown: TCP, ARP, IP total counts
- Topology: graph nodes, edges, outdegree, density
- Traffic Timing: duration, IAT mean/variance
- Capacity Flags: benign, beaconing, port scan

The agent should fill in the capacity_audit.csv template with computed values.
"""

import csv
from pathlib import Path

import pytest

# Path to the results CSV file that the agent should fill in
RESULTS_FILE = Path("/root/capacity_audit.csv")
PCAP_FILE = Path("/root/packets.pcap")

# Tolerance for floating point comparisons
TOLERANCE = 0.5
TOLERANCE_PERCENT = 0.01  # 1% tolerance for large numbers

# ============================================================
# GROUNDTRUTH VALUES (metric_name -> expected_value)
# ============================================================

EXPECTED_VALUES = {
    # Bandwidth & Payload
    "total_bytes": 30889470,
    "avg_packet_size": 270.73,
    "max_packet_size": 56538,
    # Protocol Breakdown
    "protocol_tcp": 32620,
    "protocol_arp": 54938,
    "protocol_ip_total": 58474,
    # Topology Overview
    "num_nodes": 38,
    "num_edges": 58,
    "max_outdegree": 27,
    "network_density": 0.041252,
    # Traffic Timing
    "duration_seconds": 26030.33,
    "iat_mean": 0.22814,
    "iat_variance": 0.063282,
    # Capacity Flags
    "is_traffic_benign": "true",
    "has_beaconing": "false",
    "has_port_scan": "false",
}

# Metrics that require exact integer match
EXACT_MATCH_METRICS = {
    "total_bytes",
    "max_packet_size",
    "protocol_tcp",
    "protocol_arp",
    "protocol_ip_total",
    "num_nodes",
    "num_edges",
    "max_outdegree",
}

# Boolean/categorical metrics (exact string match)
ANALYSIS_METRICS = {
    "is_traffic_benign",
    "has_beaconing",
    "has_port_scan",
}


# Cache for loaded results
_results_cache = None


def load_results():
    """
    Load the results CSV file produced by the agent.

    Returns a dict mapping metric names to values.
    Skips comment lines (starting with #).
    """
    global _results_cache
    if _results_cache is not None:
        return _results_cache

    if not RESULTS_FILE.exists():
        return None

    results = {}
    with open(RESULTS_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            metric = row.get("metric") or ""
            metric = metric.strip()
            value_str = row.get("value") or ""
            value_str = value_str.strip()

            # Skip comments and empty rows
            if not metric or metric.startswith("#") or not value_str:
                continue

            # Parse value
            try:
                if "." not in value_str:
                    results[metric] = int(value_str)
                else:
                    results[metric] = float(value_str)
            except ValueError:
                results[metric] = value_str

    _results_cache = results
    return results


def get_tolerance(metric_name, expected_value):
    """Get appropriate tolerance for a metric."""
    if metric_name in EXACT_MATCH_METRICS:
        return 0
    if isinstance(expected_value, int) and expected_value > 1000:
        return expected_value * TOLERANCE_PERCENT
    return TOLERANCE


def approx_equal(actual, expected, metric_name):
    """Check if two values are approximately equal based on metric type."""
    tolerance = get_tolerance(metric_name, expected)
    return abs(actual - expected) <= tolerance


# ============================================================
# TEST CLASSES
# ============================================================


class TestBandwidthPayload:
    """Test bandwidth and payload size measurements."""

    @pytest.mark.parametrize(
        "metric",
        [
            "total_bytes",
            "avg_packet_size",
            "max_packet_size",
        ],
    )
    def test_bandwidth_metric(self, metric):
        """Verify bandwidth/payload statistics."""
        results = load_results()
        assert results is not None, "Results file not found"
        assert metric in results, f"Missing metric: {metric}"
        assert approx_equal(
            results[metric], EXPECTED_VALUES[metric], metric
        ), f"{metric}: expected {EXPECTED_VALUES[metric]}, got {results[metric]}"


class TestProtocolBreakdown:
    """Test protocol distribution measurements."""

    @pytest.mark.parametrize(
        "metric",
        [
            "protocol_tcp",
            "protocol_arp",
            "protocol_ip_total",
        ],
    )
    def test_protocol_count(self, metric):
        """Verify protocol packet counts."""
        results = load_results()
        assert results is not None, "Results file not found"
        assert metric in results, f"Missing metric: {metric}"
        assert approx_equal(
            results[metric], EXPECTED_VALUES[metric], metric
        ), f"{metric}: expected {EXPECTED_VALUES[metric]}, got {results[metric]}"


class TestTopologyOverview:
    """Test network graph topology measurements."""

    @pytest.mark.parametrize(
        "metric",
        [
            "num_nodes",
            "num_edges",
            "max_outdegree",
        ],
    )
    def test_topology_metric(self, metric):
        """Verify graph topology measurements."""
        results = load_results()
        assert results is not None, "Results file not found"
        assert metric in results, f"Missing metric: {metric}"
        assert approx_equal(
            results[metric], EXPECTED_VALUES[metric], metric
        ), f"{metric}: expected {EXPECTED_VALUES[metric]}, got {results[metric]}"

    def test_network_density(self):
        """Verify network density calculation."""
        results = load_results()
        assert results is not None, "Results file not found"
        metric = "network_density"
        assert metric in results, f"Missing metric: {metric}"
        assert (
            abs(results[metric] - EXPECTED_VALUES[metric]) < 0.001
        ), f"{metric}: expected {EXPECTED_VALUES[metric]}, got {results[metric]}"


class TestTrafficTiming:
    """Test traffic timing measurements."""

    def test_duration_seconds(self):
        """Verify capture duration."""
        results = load_results()
        assert results is not None, "Results file not found"
        metric = "duration_seconds"
        assert metric in results, f"Missing metric: {metric}"
        assert approx_equal(
            results[metric], EXPECTED_VALUES[metric], metric
        ), f"{metric}: expected {EXPECTED_VALUES[metric]}, got {results[metric]}"

    def test_iat_mean(self):
        """Verify mean inter-arrival time."""
        results = load_results()
        assert results is not None, "Results file not found"
        metric = "iat_mean"
        assert metric in results, f"Missing metric: {metric}"
        assert (
            abs(results[metric] - EXPECTED_VALUES[metric]) < 0.01
        ), f"{metric}: expected {EXPECTED_VALUES[metric]}, got {results[metric]}"

    def test_iat_variance(self):
        """Verify inter-arrival time variance."""
        results = load_results()
        assert results is not None, "Results file not found"
        metric = "iat_variance"
        assert metric in results, f"Missing metric: {metric}"
        assert (
            abs(results[metric] - EXPECTED_VALUES[metric]) < 0.1
        ), f"{metric}: expected {EXPECTED_VALUES[metric]}, got {results[metric]}"


class TestCapacityFlags:
    """Test capacity planning analysis flags."""

    def test_is_traffic_benign(self):
        """Verify agent correctly identifies traffic as benign."""
        results = load_results()
        assert results is not None, "Results file not found"
        metric = "is_traffic_benign"
        assert metric in results, f"Missing metric: {metric}"
        actual = str(results[metric]).lower().strip()
        expected = EXPECTED_VALUES[metric]
        assert actual == expected, f"{metric}: expected '{expected}', got '{actual}'"

    def test_has_beaconing(self):
        """Verify agent correctly identifies absence of C2 beaconing."""
        results = load_results()
        assert results is not None, "Results file not found"
        metric = "has_beaconing"
        assert metric in results, f"Missing metric: {metric}"
        actual = str(results[metric]).lower().strip()
        expected = EXPECTED_VALUES[metric]
        assert actual == expected, f"{metric}: expected '{expected}', got '{actual}'"

    def test_has_port_scan(self):
        """Verify agent correctly identifies absence of port scanning."""
        results = load_results()
        assert results is not None, "Results file not found"
        metric = "has_port_scan"
        assert metric in results, f"Missing metric: {metric}"
        actual = str(results[metric]).lower().strip()
        expected = EXPECTED_VALUES[metric]
        assert actual == expected, f"{metric}: expected '{expected}', got '{actual}'"
