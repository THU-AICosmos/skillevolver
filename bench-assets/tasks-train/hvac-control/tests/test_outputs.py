#!/usr/bin/env python3
"""
Test suite for Industrial Oven Control task.
Tests only what is explicitly specified in instruction.md.
"""

import json
import os
import pytest
import numpy as np

ROOT_DIR = "/root"
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
STEP_RESPONSE_LOG = os.path.join(ROOT_DIR, "step_response_log.json")
SYSTEM_PARAMS = os.path.join(ROOT_DIR, "system_params.json")
CONTROLLER_CONFIG = os.path.join(ROOT_DIR, "controller_config.json")
REGULATION_LOG = os.path.join(ROOT_DIR, "regulation_log.json")
PERFORMANCE = os.path.join(ROOT_DIR, "performance.json")
VERIFICATION_PARAMS = os.path.join(TESTS_DIR, "verification_params.json")


def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)


def get_true_params():
    return load_json(VERIFICATION_PARAMS)


def compute_metrics_from_regulation_log(reg_data, target):
    """Compute metrics from regulation_log data for verification."""
    temperatures = [d["temperature"] for d in reg_data]
    times = [d["time"] for d in reg_data]

    if len(temperatures) == 0:
        return None

    T_initial = temperatures[0]
    start_time = times[0]
    max_temp = max(temperatures)

    # Overshoot: max temp above target relative to temperature change
    if max_temp > target and target != T_initial:
        overshoot = (max_temp - target) / (target - T_initial)
    else:
        overshoot = 0.0

    # Settling time: time to reach and stay within +/-2C of target
    settling_band = 2.0
    settling_time = None
    for i in range(len(temperatures) - 1, -1, -1):
        if abs(temperatures[i] - target) > settling_band:
            if i < len(temperatures) - 1:
                settling_time = times[i + 1] - start_time
            break
    if settling_time is None:
        settling_time = 0.0

    # Steady-state error: average error in last 25% of data
    last_portion = max(1, int(len(temperatures) * 0.25))
    steady_state_temps = temperatures[-last_portion:]
    steady_state_error = abs(np.mean(steady_state_temps) - target)

    # Duration
    duration = times[-1] - times[0] if len(times) > 1 else 0.0

    return {
        "max_temp": max_temp,
        "overshoot": overshoot,
        "settling_time": settling_time,
        "steady_state_error": steady_state_error,
        "duration": duration
    }


class TestStepResponseLog:
    """Verify step_response_log.json structure and requirements from instruction.md."""

    def test_step_response_log(self):
        """Verify step_response_log.json structure and data requirements."""
        data = load_json(STEP_RESPONSE_LOG)

        # Check phase field
        assert "phase" in data, "missing 'phase' field"
        assert data["phase"] == "characterization", f"phase should be 'characterization', got '{data['phase']}'"

        # Check element_power_test field
        assert "element_power_test" in data, "missing 'element_power_test' field"
        assert isinstance(data["element_power_test"], (int, float)), "element_power_test must be a number"
        assert data["element_power_test"] > 0, "element_power_test must be positive"

        # Check data array exists and is not empty
        assert "data" in data, "missing 'data' field"
        assert len(data["data"]) > 0, "data array is empty"

        # Check each data entry has required fields
        for i, entry in enumerate(data["data"]):
            assert "time" in entry, f"entry {i} missing 'time'"
            assert "temperature" in entry, f"entry {i} missing 'temperature'"
            assert "element_power" in entry, f"entry {i} missing 'element_power'"

        # Check at least 25 data points
        assert len(data["data"]) >= 25, f"need at least 25 data points, got {len(data['data'])}"

        # Check at least 40 seconds of data
        times = [entry["time"] for entry in data["data"]]
        duration = times[-1] - times[0]
        assert duration >= 40.0, f"need at least 40 seconds of data, got {duration:.1f}s"

        # Check timestamps are monotonic
        for i in range(1, len(times)):
            assert times[i] > times[i-1], f"timestamps not monotonic at index {i}"

        # Check first reading is near ambient
        first_temp = data["data"][0]["temperature"]
        assert abs(first_temp - 25.0) <= 3.0, f"first reading should be within +/-3C of 25C, got {first_temp}C"

        # Check data uses declared power
        declared = data["element_power_test"]
        matches = [e for e in data["data"] if abs(e["element_power"] - declared) < 0.1]
        assert len(matches) > 0, f"no data entries use declared element_power_test={declared}"


class TestSystemParams:
    """Verify system_params.json structure and accuracy requirements from instruction.md."""

    def test_system_params(self):
        """Verify system_params.json structure and accuracy."""
        params = load_json(SYSTEM_PARAMS)
        true_params = get_true_params()

        # Check required fields exist
        for field in ["K", "tau", "r_squared", "fitting_error"]:
            assert field in params, f"missing '{field}' field"

        # Check no NaN values
        assert not np.isnan(params["K"]), "K is NaN"
        assert not np.isnan(params["tau"]), "tau is NaN"
        assert not np.isnan(params["r_squared"]), "r_squared is NaN"
        assert not np.isnan(params["fitting_error"]), "fitting_error is NaN"

        # Check K within +/-15% tolerance
        K_true = true_params["process_gain_K"]
        K_est = params["K"]
        error = abs(K_est - K_true) / K_true
        assert error <= 0.15, f"K error {error*100:.1f}% exceeds 15% tolerance"

        # Check tau within +/-20% tolerance
        tau_true = true_params["time_constant_tau"]
        tau_est = params["tau"]
        error = abs(tau_est - tau_true) / tau_true
        assert error <= 0.20, f"tau error {error*100:.1f}% exceeds 20% tolerance"

        # Check R^2 exceeds 0.8
        assert params["r_squared"] > 0.8, f"R^2 = {params['r_squared']} should be > 0.8"


class TestControllerConfig:
    """Verify controller_config.json structure and range requirements from instruction.md."""

    def test_controller_config(self):
        """Verify controller_config.json structure and value ranges."""
        gains = load_json(CONTROLLER_CONFIG)

        # Check required fields exist
        for field in ["Kp", "Ki", "Kd", "lambda"]:
            assert field in gains, f"missing '{field}' field"

        # Check Kp in range (0.1, 50)
        assert 0.1 < gains["Kp"] < 50, f"Kp={gains['Kp']} must be between 0.1 and 50 (exclusive)"

        # Check Ki in range (0.001, 2)
        assert 0.001 < gains["Ki"] < 2, f"Ki={gains['Ki']} must be between 0.001 and 2 (exclusive)"

        # Check Kd is non-negative
        assert gains["Kd"] >= 0, f"Kd={gains['Kd']} must be non-negative"

        # Check lambda is positive
        assert gains["lambda"] > 0, f"lambda={gains['lambda']} must be positive"


class TestRegulationLog:
    """Verify regulation_log.json structure and requirements from instruction.md."""

    def test_regulation_log(self):
        """Verify regulation_log.json structure and data requirements."""
        data = load_json(REGULATION_LOG)

        # Check phase field
        assert "phase" in data, "missing 'phase' field"
        assert data["phase"] == "regulation", f"phase should be 'regulation', got '{data['phase']}'"

        # Check target field
        assert "target" in data, "missing 'target' field"
        assert data["target"] == 65.0, f"target should be 65.0, got {data['target']}"

        # Check data array exists and is not empty
        assert "data" in data, "missing 'data' field"
        assert len(data["data"]) > 0, "data array is empty"

        # Check each data entry has required fields
        for i, entry in enumerate(data["data"][:10]):
            assert "time" in entry, f"entry {i} missing 'time'"
            assert "temperature" in entry, f"entry {i} missing 'temperature'"
            assert "target" in entry, f"entry {i} missing 'target'"
            assert "element_power" in entry, f"entry {i} missing 'element_power'"
            assert "error" in entry, f"entry {i} missing 'error'"

        # Check at least 200 seconds of data
        times = [entry["time"] for entry in data["data"]]
        duration = times[-1] - times[0]
        assert duration >= 200.0, f"need at least 200 seconds, got {duration:.1f}s"

        # Check timestamps are monotonic
        for i in range(1, len(times)):
            assert times[i] > times[i-1], f"timestamps not monotonic at index {i}"


class TestPerformance:
    """Verify performance.json structure and consistency with regulation_log.json."""

    def test_performance(self):
        """Verify performance.json structure and consistency with regulation_log."""
        perf = load_json(PERFORMANCE)
        regulation = load_json(REGULATION_LOG)
        computed = compute_metrics_from_regulation_log(regulation["data"], 65.0)

        # Check required fields exist
        for field in ["rise_time", "overshoot", "settling_time", "steady_state_error", "max_temp"]:
            assert field in perf, f"missing '{field}' field"

        # Check max_temp matches regulation_log
        actual_max = max(e["temperature"] for e in regulation["data"])
        assert abs(perf["max_temp"] - actual_max) < 0.5, \
            f"max_temp ({perf['max_temp']}) doesn't match regulation_log ({actual_max})"

        # Check overshoot matches regulation_log
        assert abs(perf["overshoot"] - computed["overshoot"]) < 0.05, \
            f"overshoot ({perf['overshoot']}) doesn't match computed ({computed['overshoot']})"

        # Check steady_state_error matches regulation_log
        assert abs(perf["steady_state_error"] - computed["steady_state_error"]) < 0.2, \
            f"steady_state_error ({perf['steady_state_error']}) doesn't match computed ({computed['steady_state_error']})"


class TestPerformanceTargets:
    """Verify control performance meets targets from instruction.md."""

    def test_performance_targets(self):
        """Verify control performance meets all targets."""
        regulation = load_json(REGULATION_LOG)
        computed = compute_metrics_from_regulation_log(regulation["data"], 65.0)

        # Check steady-state error within 0.3C
        assert computed["steady_state_error"] <= 0.3, \
            f"steady-state error {computed['steady_state_error']:.3f}C exceeds 0.3C"

        # Check settling time under 180 seconds
        assert computed["settling_time"] <= 180.0, \
            f"settling time {computed['settling_time']:.1f}s exceeds 180s"

        # Check overshoot within 8%
        assert computed["overshoot"] <= 0.08, \
            f"overshoot {computed['overshoot']*100:.1f}% exceeds 8%"

        # Check max temperature below 85C
        assert computed["max_temp"] < 85.0, \
            f"max temperature {computed['max_temp']:.2f}C exceeds 85C"


class TestSafety:
    """Verify temperature stays below 85C during all phases per instruction."""

    def test_safety(self):
        """Verify temperature stays below 85C during all phases."""
        # Check characterization phase
        step_data = load_json(STEP_RESPONSE_LOG)
        for entry in step_data["data"]:
            assert entry["temperature"] < 85.0, \
                f"temperature {entry['temperature']}C exceeded 85C at t={entry['time']}s during characterization"

        # Check regulation phase
        regulation_data = load_json(REGULATION_LOG)
        for entry in regulation_data["data"]:
            assert entry["temperature"] < 85.0, \
                f"temperature {entry['temperature']}C exceeded 85C at t={entry['time']}s during regulation"
