#!/bin/bash
set -e

cd /root

python3 << 'EOF'
#!/usr/bin/env python3
"""
Oracle solution for Industrial Oven Temperature Control task.

This script:
1. Performs a step-response characterization of the oven
2. Estimates first-order model parameters (K, tau) via curve fitting
3. Derives IMC-based PI controller gains
4. Executes closed-loop temperature regulation to target
5. Outputs all required JSON result files
"""

import json
import numpy as np
from scipy.optimize import curve_fit
from oven_simulator import OvenSimulator


class OvenCharacterizer:
    """Handles open-loop step testing for system identification."""

    def __init__(self, simulator, test_power=60.0):
        self.sim = simulator
        self.test_power = test_power
        self.max_temp = simulator.get_safety_limits()["max_temp"]

    def execute(self, total_duration=120.0, idle_seconds=8.0):
        dt = self.sim.get_dt()
        readings = []

        self.sim.reset()

        # Idle phase - no heating
        for _ in range(int(idle_seconds / dt)):
            obs = self.sim.step(0.0)
            readings.append({
                "time": obs["time"],
                "temperature": obs["temperature"],
                "element_power": obs["element_power"]
            })

        # Active heating phase
        pwr = self.test_power
        active_steps = int((total_duration - idle_seconds) / dt)
        for _ in range(active_steps):
            if readings[-1]["temperature"] >= self.max_temp:
                pwr = 0.0
            obs = self.sim.step(pwr)
            readings.append({
                "time": obs["time"],
                "temperature": obs["temperature"],
                "element_power": obs["element_power"]
            })

        return readings


class FirstOrderEstimator:
    """Fits a first-order model to step response data."""

    def __init__(self, ambient_temp, input_power):
        self.T0 = ambient_temp
        self.u = input_power

    def _model_fn(self, t, gain, tc):
        return self.T0 + gain * self.u * (1 - np.exp(-t / tc))

    def fit(self, readings):
        # Find the start of the step input
        onset_idx = None
        for idx, r in enumerate(readings):
            if r["element_power"] > 0:
                onset_idx = idx
                break

        if onset_idx is None:
            raise RuntimeError("No active step input detected in characterization data")

        active = readings[onset_idx:]
        t0_val = active[0]["time"]
        tvec = np.array([r["time"] - t0_val for r in active])
        yvec = np.array([r["temperature"] for r in active])

        # Compute initial parameter estimates
        y_end = yvec[-1]
        gain_init = (y_end - self.T0) / self.u
        tc_init = 40.0

        try:
            popt, _ = curve_fit(
                self._model_fn, tvec, yvec,
                p0=[gain_init, tc_init],
                bounds=([0.005, 3], [1.0, 300]),
                maxfev=8000
            )
            gain_est, tc_est = popt
        except Exception:
            gain_est, tc_est = gain_init, tc_init

        # Goodness of fit
        y_hat = self._model_fn(tvec, gain_est, tc_est)
        resid = yvec - y_hat
        ss_r = np.sum(resid ** 2)
        ss_t = np.sum((yvec - np.mean(yvec)) ** 2)
        r2 = 1.0 - (ss_r / ss_t) if ss_t > 0 else 0.0
        rmse = np.sqrt(np.mean(resid ** 2))

        return {
            "K": float(gain_est),
            "tau": float(tc_est),
            "r_squared": float(r2),
            "fitting_error": float(rmse)
        }


class IMCTuner:
    """Computes PI gains via IMC tuning rules."""

    @staticmethod
    def compute_gains(gain, tc, aggressiveness=1.0):
        lam = aggressiveness * tc
        kp = tc / (gain * lam)
        ki = kp / tc
        return {
            "Kp": float(kp),
            "Ki": float(ki),
            "Kd": 0.0,
            "lambda": float(lam)
        }


class PIRegulator:
    """Closed-loop PI controller with safety interlocks."""

    def __init__(self, simulator, kp, ki, target, max_temp):
        self.sim = simulator
        self.kp = kp
        self.ki = ki
        self.target = target
        self.max_temp = max_temp
        self.integral_sum = 0.0

    def run(self, run_duration=205.0):
        dt = self.sim.get_dt()
        log = []
        prev_temp = None

        for _ in range(int(run_duration / dt)):
            if prev_temp is None:
                obs = self.sim.step(0.0)
                prev_temp = obs["temperature"]

            temp = prev_temp
            err = self.target - temp
            self.integral_sum += err * dt
            self.integral_sum = np.clip(self.integral_sum, -800, 800)

            cmd = self.kp * err + self.ki * self.integral_sum

            if temp >= self.max_temp:
                cmd = 0.0
                self.integral_sum = 0.0

            cmd = np.clip(cmd, 0.0, 100.0)

            obs = self.sim.step(cmd)
            prev_temp = obs["temperature"]

            log.append({
                "time": obs["time"],
                "temperature": obs["temperature"],
                "target": self.target,
                "element_power": obs["element_power"],
                "error": float(self.target - obs["temperature"])
            })

        return log


def evaluate_performance(log_data, target):
    """Compute performance metrics from regulation log."""
    temps = [d["temperature"] for d in log_data]
    tvals = [d["time"] for d in log_data]

    t_init = temps[0]
    peak_temp = max(temps)

    # Rise time: time to 90% of target change
    threshold_90 = t_init + 0.9 * (target - t_init)
    rt = None
    for j, t in enumerate(temps):
        if t >= threshold_90:
            rt = tvals[j] - tvals[0]
            break
    if rt is None:
        rt = tvals[-1] - tvals[0]

    # Overshoot
    if peak_temp > target and target != t_init:
        os_val = (peak_temp - target) / (target - t_init)
    else:
        os_val = 0.0

    # Settling time (+/- 2C band)
    band = 2.0
    st = None
    for j in range(len(temps) - 1, -1, -1):
        if abs(temps[j] - target) > band:
            if j < len(temps) - 1:
                st = tvals[j + 1] - tvals[0]
            break
    if st is None:
        st = 0.0

    # Steady-state error (last 25%)
    n_tail = max(1, int(len(temps) * 0.25))
    tail = temps[-n_tail:]
    sse = abs(np.mean(tail) - target)

    return {
        "rise_time": float(rt),
        "overshoot": float(os_val),
        "settling_time": float(st),
        "steady_state_error": float(sse),
        "max_temp": float(peak_temp)
    }


def main():
    print("=== Industrial Oven Control - Oracle Solution ===\n")

    oven = OvenSimulator()
    target = oven.get_target_temp()
    ambient = oven.get_ambient_temp()
    safety = oven.get_safety_limits()

    print(f"Target temperature: {target}C")
    print(f"Ambient temperature: {ambient}C")
    print(f"Safety limit: {safety['max_temp']}C\n")

    # Phase 1: Characterization via step response
    print("Phase 1: Running oven characterization...")
    test_pwr = 60.0
    characterizer = OvenCharacterizer(oven, test_power=test_pwr)
    char_data = characterizer.execute(total_duration=120.0)

    with open("step_response_log.json", "w") as fp:
        json.dump({
            "phase": "characterization",
            "element_power_test": test_pwr,
            "data": char_data
        }, fp, indent=2)
    print(f"  Saved step_response_log.json ({len(char_data)} samples)")

    # Phase 2: Parameter Estimation
    print("\nPhase 2: Estimating system parameters...")
    estimator = FirstOrderEstimator(ambient, test_pwr)
    sys_params = estimator.fit(char_data)

    with open("system_params.json", "w") as fp:
        json.dump(sys_params, fp, indent=2)
    print(f"  K = {sys_params['K']:.4f} C/%")
    print(f"  tau = {sys_params['tau']:.2f} s")
    print(f"  R^2 = {sys_params['r_squared']:.4f}")

    # Phase 3: Controller Design
    print("\nPhase 3: Computing PI controller gains...")
    ctrl_gains = IMCTuner.compute_gains(
        sys_params["K"], sys_params["tau"], aggressiveness=0.35
    )

    with open("controller_config.json", "w") as fp:
        json.dump(ctrl_gains, fp, indent=2)
    print(f"  Kp = {ctrl_gains['Kp']:.4f}")
    print(f"  Ki = {ctrl_gains['Ki']:.4f}")
    print(f"  lambda = {ctrl_gains['lambda']:.2f} s")

    # Phase 4: Closed-Loop Regulation
    print("\nPhase 4: Running closed-loop regulation...")
    regulator = PIRegulator(
        oven, ctrl_gains["Kp"], ctrl_gains["Ki"],
        target, safety["max_temp"]
    )
    reg_data = regulator.run(run_duration=280.0)

    with open("regulation_log.json", "w") as fp:
        json.dump({
            "phase": "regulation",
            "target": target,
            "data": reg_data
        }, fp, indent=2)
    print(f"  Saved regulation_log.json ({len(reg_data)} samples)")

    # Compute and save performance metrics
    print("\nComputing performance metrics...")
    perf = evaluate_performance(reg_data, target)

    with open("performance.json", "w") as fp:
        json.dump(perf, fp, indent=2)

    print(f"  Rise time: {perf['rise_time']:.2f} s")
    print(f"  Overshoot: {perf['overshoot']*100:.1f}%")
    print(f"  Settling time: {perf['settling_time']:.2f} s")
    print(f"  Steady-state error: {perf['steady_state_error']:.3f} C")
    print(f"  Max temperature: {perf['max_temp']:.2f} C")

    print("\n=== Solution complete ===")


if __name__ == "__main__":
    main()
EOF

echo "Oracle solution completed successfully."
