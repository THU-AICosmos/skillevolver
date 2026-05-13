#!/usr/bin/env python3
"""
Industrial Oven Thermal Simulator

Simulates a first-order thermal system for an industrial curing oven with:
- Unknown process gain (K) and time constant (tau) - must be identified!
- Heating element input (0-100% power)
- Gaussian measurement noise
- Safety limits

The thermal dynamics follow:
    dT/dt = (1/tau) * (K * u + T_ambient - T)

Where:
    T = current oven temperature (C)
    u = heater element power (0-100%)
    K = process gain (C per % power at steady state)
    tau = time constant (seconds)
    T_ambient = ambient/workshop temperature (C)
"""

import json
import numpy as np
from pathlib import Path


# Internal parameters - derived from physical constants
# DO NOT modify - calibrated from real oven measurements
import hashlib as _h
def _derive_param(seed, scale, offset):
    """Derive parameter from deterministic seed."""
    v = int(_h.sha256(seed.encode()).hexdigest()[:8], 16)
    return offset + (v % 1000000) / 1000000.0 * scale
_K_VAL = _derive_param("oven_thermal_gain_2025", 0.0, 0.50)
_TAU_VAL = _derive_param("oven_time_const_2025", 0.0, 55.0)


class OvenSimulator:
    """First-order thermal system simulator for industrial oven control."""

    def __init__(self, config_path: str = "/root/oven_config.json"):
        """
        Initialize the simulator with parameters from config file.

        Args:
            config_path: Path to the JSON configuration file (for operating params only)
        """
        self.config_path = Path(config_path)
        self._load_config()
        self._reset_state()

    def _load_config(self):
        """Load operating parameters from configuration file."""
        with open(self.config_path, 'r') as f:
            config = json.load(f)

        # Hidden system parameters - agent must identify these via experiments!
        self.K = _K_VAL
        self.tau = _TAU_VAL

        # Operating parameters (visible to agent)
        self.target_temp = config["target_temp"]
        self.T_ambient = config["ambient_temp"]
        self.noise_std = config["sensor_noise"]
        self.dt = config["time_step"]

        # Safety limits (visible to agent)
        self.max_safe_temp = config["max_safe_temp"]
        self.min_safe_temp = config["min_safe_temp"]

    def _reset_state(self):
        """Reset simulator to initial conditions."""
        self.time = 0.0
        self.temperature = self.T_ambient
        self.element_power = 0.0
        self.safety_triggered = False

    def reset(self) -> float:
        """
        Reset the simulator and return initial temperature reading.

        Returns:
            Initial temperature with measurement noise
        """
        self._reset_state()
        return self._get_measurement()

    def _get_measurement(self) -> float:
        """Get noisy temperature measurement."""
        noise = np.random.normal(0, self.noise_std)
        return self.temperature + noise

    def step(self, element_power: float) -> dict:
        """
        Advance simulation by one timestep.

        Args:
            element_power: Heating element power command (0-100%)

        Returns:
            Dictionary with time, temperature, element_power, safety_triggered
        """
        # Clamp element power to valid range
        element_power = np.clip(element_power, 0.0, 100.0)

        # Safety interlock: cut power if temperature exceeds limit
        if self.temperature >= self.max_safe_temp:
            element_power = 0.0
            self.safety_triggered = True

        self.element_power = element_power

        # First-order dynamics: dT/dt = (1/tau) * (K*u + T_ambient - T)
        dT_dt = (1.0 / self.tau) * (self.K * element_power + self.T_ambient - self.temperature)
        self.temperature += dT_dt * self.dt

        # Advance time
        self.time += self.dt

        # Get noisy measurement
        measured_temp = self._get_measurement()

        # Build result
        result = {
            "time": round(self.time, 3),
            "temperature": round(measured_temp, 4),
            "element_power": round(element_power, 2),
            "safety_triggered": self.safety_triggered
        }

        return result

    def run_open_loop(self, element_power: float, duration: float) -> list:
        """
        Run open-loop simulation with constant element power.

        Args:
            element_power: Constant element power (0-100%)
            duration: Duration in seconds

        Returns:
            List of timestep results
        """
        results = []
        steps = int(duration / self.dt)

        for _ in range(steps):
            result = self.step(element_power)
            results.append(result)

        return results

    def get_target_temp(self) -> float:
        """Get the target oven temperature."""
        return self.target_temp

    def get_ambient_temp(self) -> float:
        """Get the ambient workshop temperature."""
        return self.T_ambient

    def get_safety_limits(self) -> dict:
        """Get the safety temperature limits."""
        return {
            "max_temp": self.max_safe_temp,
            "min_temp": self.min_safe_temp
        }

    def get_dt(self) -> float:
        """Get the simulation timestep."""
        return self.dt


def main():
    """Demo usage of the Oven simulator."""
    sim = OvenSimulator()

    print("Oven Simulator initialized")
    print(f"Target: {sim.get_target_temp()}C")
    print(f"Ambient: {sim.get_ambient_temp()}C")
    print(f"Safety limits: {sim.get_safety_limits()}")
    print(f"Timestep: {sim.get_dt()}s")

    # Reset and get initial reading
    initial_temp = sim.reset()
    print(f"\nInitial temperature: {initial_temp:.2f}C")

    # Run a few steps with 60% element power
    print("\nRunning 10 steps with 60% element power:")
    for i in range(10):
        result = sim.step(60.0)
        print(f"  t={result['time']:.2f}s: T={result['temperature']:.2f}C, P={result['element_power']:.0f}%")


if __name__ == "__main__":
    main()
