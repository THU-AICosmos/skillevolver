"""
Tests for the dapt-intrusion-detection TRAIN variant.

This variant uses a synthetic cloud-tenant web-service capture (different IP ranges,
different protocol mix, different values) from the validation task.  The agent must
fill in /root/network_analysis.csv with the metrics listed in the template.

Coverage mirrors the validation spec's breadth (8 sections, 39 metrics):
- Volume and Protocol Mix  (incl. protocol_arp, dominant_protocol)
- Byte Counters and Frame Sizes
- Capture Rate
- Endpoint Diversity (Shannon entropy)
- Conversation Graph (directed IP graph)
- Inter-Arrival and Role Analysis
- 5-Tuple Flow Enumeration
- Threat Indicators (boolean flags)

Heuristics exercised on this pcap:
- port_scan_flag: single scanner hits 150 unique dst ports with SYN-only.
- dos_spike_flag: burst minute dominates the mean (>20x ratio).
- beaconing_flag: single UDP 5-tuple carries 15 packets at 2.0 s cadence.
"""

import csv
from pathlib import Path

import pytest

RESULTS_FILE = Path("/root/network_analysis.csv")
PCAP_FILE = Path("/root/packets.pcap")

# Tolerance bands
TOLERANCE = 0.5
TOLERANCE_PERCENT = 0.01     # 1% tolerance for large integer counts
ENTROPY_TOLERANCE = 0.05     # 5% tolerance for Shannon entropy

# ---------------------------------------------------------------------------
# Ground truth (computed by the oracle on /root/packets.pcap)
# ---------------------------------------------------------------------------

EXPECTED_VALUES = {
    # Volume and Protocol Mix
    "frame_count": 2800,
    "tcp_packet_count": 786,
    "udp_packet_count": 589,
    "icmp_packet_count": 300,
    "protocol_arp": 1125,
    "protocol_ip_total": 1675,
    "dominant_protocol": "arp",
    # Byte Counters and Frame Sizes
    "total_octets": 196120,
    "mean_frame_length": 70.04,
    "smallest_frame": 42,
    "largest_frame": 954,
    # Capture Rate
    "capture_span_seconds": 3309.05,
    "peak_minute_rate": 1215,
    "mean_minute_rate": 50.0,
    "floor_minute_rate": 2,
    # Endpoint Diversity
    "dest_port_entropy": 7.3348,
    "source_port_entropy": 8.2173,
    "source_ip_entropy": 3.8022,
    "dest_ip_entropy": 3.6291,
    "unique_dest_ports": 510,
    "unique_source_ports": 902,
    # Conversation Graph
    "host_count": 21,
    "conversation_edges": 150,
    "graph_density": 0.357143,
    "max_fanin": 16,
    "max_fanout": 15,
    # Inter-Arrival and Role Analysis
    "interarrival_mean": 1.182226,
    "interarrival_variance": 32.65402,
    "interarrival_cv": 4.8336,
    "producer_hosts": 5,
    "consumer_hosts": 2,
    # 5-Tuple Flow Enumeration
    "distinct_flows": 1249,
    "tcp_flow_count": 674,
    "udp_flow_count": 575,
    "paired_flows": 351,
    # Threat Indicators
    "benign_traffic_flag": "false",
    "port_scan_flag": "true",
    "dos_spike_flag": "true",
    "beaconing_flag": "true",
}

EXACT_MATCH_METRICS = {
    "frame_count",
    "tcp_packet_count",
    "udp_packet_count",
    "icmp_packet_count",
    "protocol_arp",
    "protocol_ip_total",
    "smallest_frame",
    "largest_frame",
    "peak_minute_rate",
    "floor_minute_rate",
    "unique_dest_ports",
    "unique_source_ports",
    "host_count",
    "conversation_edges",
    "max_fanin",
    "max_fanout",
    "producer_hosts",
    "consumer_hosts",
    "distinct_flows",
    "tcp_flow_count",
    "udp_flow_count",
    "paired_flows",
}

ENTROPY_METRICS = {
    "dest_port_entropy",
    "source_port_entropy",
    "source_ip_entropy",
    "dest_ip_entropy",
}

STRING_METRICS = {
    "dominant_protocol",
    "benign_traffic_flag",
    "port_scan_flag",
    "dos_spike_flag",
    "beaconing_flag",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_results_cache = None


def load_results():
    global _results_cache
    if _results_cache is not None:
        return _results_cache
    if not RESULTS_FILE.exists():
        return None

    parsed = {}
    with open(RESULTS_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            metric = (row.get("metric") or "").strip()
            value_str = (row.get("value") or "").strip()
            if not metric or metric.startswith("#") or not value_str:
                continue
            try:
                if "." not in value_str:
                    parsed[metric] = int(value_str)
                else:
                    parsed[metric] = float(value_str)
            except ValueError:
                parsed[metric] = value_str
    _results_cache = parsed
    return parsed


def get_tolerance(metric_name, expected_value):
    if metric_name in EXACT_MATCH_METRICS:
        return 0
    if metric_name in ENTROPY_METRICS:
        return abs(expected_value) * ENTROPY_TOLERANCE
    if isinstance(expected_value, int) and expected_value > 1000:
        return expected_value * TOLERANCE_PERCENT
    return TOLERANCE


def approx_equal(actual, expected, metric_name):
    return abs(actual - expected) <= get_tolerance(metric_name, expected)


def _check_numeric(metric):
    results = load_results()
    assert results is not None, "Results file not found"
    assert metric in results, f"Missing metric: {metric}"
    assert approx_equal(
        results[metric], EXPECTED_VALUES[metric], metric
    ), f"{metric}: expected {EXPECTED_VALUES[metric]}, got {results[metric]}"


def _check_string(metric):
    results = load_results()
    assert results is not None, "Results file not found"
    assert metric in results, f"Missing metric: {metric}"
    actual = str(results[metric]).lower().strip()
    expected = EXPECTED_VALUES[metric]
    assert actual == expected, f"{metric}: expected '{expected}', got '{actual}'"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVolumeAndProtocolMix:
    @pytest.mark.parametrize(
        "metric",
        [
            "frame_count",
            "tcp_packet_count",
            "udp_packet_count",
            "icmp_packet_count",
            "protocol_arp",
            "protocol_ip_total",
        ],
    )
    def test_volume_metric(self, metric):
        _check_numeric(metric)

    def test_dominant_protocol(self):
        _check_string("dominant_protocol")


class TestByteCounters:
    @pytest.mark.parametrize(
        "metric",
        [
            "total_octets",
            "mean_frame_length",
            "smallest_frame",
            "largest_frame",
        ],
    )
    def test_byte_metric(self, metric):
        _check_numeric(metric)


class TestCaptureRate:
    @pytest.mark.parametrize(
        "metric",
        [
            "capture_span_seconds",
            "peak_minute_rate",
            "mean_minute_rate",
            "floor_minute_rate",
        ],
    )
    def test_rate_metric(self, metric):
        _check_numeric(metric)


class TestEndpointDiversity:
    @pytest.mark.parametrize(
        "metric",
        [
            "dest_port_entropy",
            "source_port_entropy",
            "source_ip_entropy",
            "dest_ip_entropy",
            "unique_dest_ports",
            "unique_source_ports",
        ],
    )
    def test_diversity_metric(self, metric):
        _check_numeric(metric)


class TestConversationGraph:
    @pytest.mark.parametrize(
        "metric",
        [
            "host_count",
            "conversation_edges",
            "max_fanin",
            "max_fanout",
        ],
    )
    def test_graph_metric(self, metric):
        _check_numeric(metric)

    def test_graph_density(self):
        results = load_results()
        assert results is not None, "Results file not found"
        assert "graph_density" in results, "Missing metric: graph_density"
        assert (
            abs(results["graph_density"] - EXPECTED_VALUES["graph_density"]) < 0.001
        ), f"graph_density: expected {EXPECTED_VALUES['graph_density']}, got {results['graph_density']}"


class TestInterarrivalAndRoles:
    @pytest.mark.parametrize(
        "metric",
        [
            "interarrival_mean",
            "interarrival_variance",
            "interarrival_cv",
            "producer_hosts",
            "consumer_hosts",
        ],
    )
    def test_temporal_metric(self, metric):
        results = load_results()
        assert results is not None, "Results file not found"
        assert metric in results, f"Missing metric: {metric}"
        if metric == "interarrival_mean":
            assert (
                abs(results[metric] - EXPECTED_VALUES[metric]) < 0.01
            ), f"{metric}: expected {EXPECTED_VALUES[metric]}, got {results[metric]}"
        elif metric == "interarrival_variance":
            # Variance depends on the square of seconds; give it a wider band.
            assert (
                abs(results[metric] - EXPECTED_VALUES[metric])
                <= max(0.1, EXPECTED_VALUES[metric] * 0.01)
            ), f"{metric}: expected {EXPECTED_VALUES[metric]}, got {results[metric]}"
        elif metric == "interarrival_cv":
            assert (
                abs(results[metric] - EXPECTED_VALUES[metric]) < 0.1
            ), f"{metric}: expected {EXPECTED_VALUES[metric]}, got {results[metric]}"
        else:
            assert approx_equal(
                results[metric], EXPECTED_VALUES[metric], metric
            ), f"{metric}: expected {EXPECTED_VALUES[metric]}, got {results[metric]}"


class TestFlowEnumeration:
    @pytest.mark.parametrize(
        "metric",
        [
            "distinct_flows",
            "tcp_flow_count",
            "udp_flow_count",
            "paired_flows",
        ],
    )
    def test_flow_metric(self, metric):
        _check_numeric(metric)


class TestThreatIndicators:
    def test_benign_traffic_flag(self):
        _check_string("benign_traffic_flag")

    def test_port_scan_flag(self):
        _check_string("port_scan_flag")

    def test_dos_spike_flag(self):
        _check_string("dos_spike_flag")

    def test_beaconing_flag(self):
        _check_string("beaconing_flag")
