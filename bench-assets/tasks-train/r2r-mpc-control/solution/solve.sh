#!/bin/bash
set -e

cd /root

python3 << 'EOF'
#!/usr/bin/env python3
"""
Oracle solution for R2R MPC Control task (4-section variant).

This script:
1. Derives linearized state-space model for the 4-section system
2. Designs MPC controller with finite-horizon LQR
3. Runs closed-loop simulation with integral action
4. Computes and saves performance metrics
"""

import json
import numpy as np
from scipy import linalg
from r2r_simulator import R2RSimulator


def build_jacobian(state, sys_params):
    """
    Derive linearized A_d, B_d at operating point.
    Based on R2R dynamics:
        dT_i/dt = (EA/L)*(v_i - v_{i-1}) + (1/L)*(v_{i-1}*T_{i-1} - v_i*T_i)
        dv_i/dt = (R^2/J)*(T_{i+1} - T_i) + (R/J)*u_i - (fb/J)*v_i
    """
    stiffness = sys_params["EA"]
    inertia = sys_params["J"]
    radius = sys_params["R"]
    friction = sys_params["fb"]
    span = sys_params["L"]
    timestep = sys_params["dt"]
    n = sys_params["num_sections"]
    nx = 2 * n

    jac_x = np.zeros((nx, nx))
    jac_u = np.zeros((nx, n))

    for sec in range(n):
        vel = state[sec + n]
        ten = state[sec]

        # Partial derivatives for tension equation
        jac_x[sec, sec] = -vel / span
        jac_x[sec, sec + n] = stiffness / span - ten / span
        if sec > 0:
            vel_prev = state[sec + n - 1]
            ten_prev = state[sec - 1]
            jac_x[sec, sec - 1] = vel_prev / span
            jac_x[sec, sec + n - 1] = -stiffness / span + ten_prev / span

        # Partial derivatives for velocity equation
        jac_x[sec + n, sec] = -radius**2 / inertia
        jac_x[sec + n, sec + n] = -friction / inertia
        if sec < n - 1:
            jac_x[sec + n, sec + 1] = radius**2 / inertia
        jac_u[sec + n, sec] = radius / inertia

    # Euler discretization
    Ad = np.eye(nx) + timestep * jac_x
    Bd = timestep * jac_u
    return Ad, Bd


def solve_lqr(Ad, Bd, Qw, Rw, timestep):
    """Compute LQR feedback gain via continuous-time ARE."""
    nx = Ad.shape[0]
    Ac = (Ad - np.eye(nx)) / timestep
    Bc = Bd / timestep
    P_are = linalg.solve_continuous_are(Ac, Bc, Qw, Rw)
    gain = np.linalg.solve(Rw, Bc.T @ P_are)
    return gain


def receding_horizon_lqr(Ad, Bd, Qw, Rw, steps, delta_x):
    """Solve finite-horizon LQR via backward Riccati recursion."""
    nx = Ad.shape[0]
    nu = Bd.shape[1]
    gains = np.zeros((nu, nx, steps - 1))
    cost_mat = Qw.copy()

    for t in range(steps - 2, -1, -1):
        gains[:, :, t] = np.linalg.solve(
            Rw + Bd.T @ cost_mat @ Bd,
            Bd.T @ cost_mat @ Ad
        )
        cost_mat = Qw + Ad.T @ cost_mat @ (Ad - Bd @ gains[:, :, t])

    return -gains[:, :, 0] @ delta_x


def setup_controller(simulator):
    """Design MPC controller parameters for 4-section system."""
    sys_p = simulator.get_params()
    n = sys_p["num_sections"]
    nx = 2 * n
    ref_state, _ = simulator.get_reference(0)
    Ad, Bd = build_jacobian(ref_state, sys_p)

    # Weighted cost design
    T_nom = 30.0
    v_nom = 0.02
    q_tensions = 1.2e2 * np.ones(n) / T_nom**2
    q_velocities = 1.5e-1 * np.ones(n) / v_nom**2
    q_diag = np.concatenate([q_tensions, q_velocities])
    r_diag = 4.0e-2 * np.ones(n)

    Qw = np.diag(q_diag)
    Rw = np.diag(r_diag)

    feedback_gain = solve_lqr(Ad, Bd, Qw, Rw, simulator.dt)

    return {
        "horizon_N": 12,
        "Q_diag": q_diag.tolist(),
        "R_diag": r_diag.tolist(),
        "K_lqr": feedback_gain.tolist(),
        "A_matrix": Ad.tolist(),
        "B_matrix": Bd.tolist()
    }


def execute_control(simulator, ctrl_cfg, sim_duration=5.0):
    """Run closed-loop MPC simulation."""
    simulator.reset()
    sys_p = simulator.get_params()
    dt = sys_p["dt"]
    n = sys_p["num_sections"]
    nx = 2 * n

    Qw = np.diag(ctrl_cfg["Q_diag"])
    Rw = np.diag(ctrl_cfg["R_diag"])
    fb_gain = np.array(ctrl_cfg["K_lqr"])
    horizon = ctrl_cfg["horizon_N"]

    log_entries = []
    ki = 0.25          # Integral coefficient
    decay = 0.93       # Leaky integrator decay
    accum = np.zeros(n)

    total_steps = int(sim_duration / dt)
    for _ in range(total_steps):
        measurement = simulator.get_state()
        target_x, target_u = simulator.get_reference()

        # Re-linearize at current reference
        Ad, Bd = build_jacobian(target_x, sys_p)

        # MPC: finite-horizon deviation control
        err = measurement - target_x
        mpc_du = receding_horizon_lqr(Ad, Bd, Qw, Rw, horizon, err)

        # Integral action for offset-free tracking
        accum = decay * accum - ki * dt * (measurement[:n] - target_x[:n])

        # Combine: feedforward + MPC + LQR feedback + integral
        command = target_u + mpc_du - fb_gain @ err + accum

        simulator.step(command)

        log_entries.append({
            "time": round(simulator.get_time(), 4),
            "tensions": measurement[:n].tolist(),
            "velocities": measurement[n:].tolist(),
            "control_inputs": command.tolist(),
            "references": target_x.tolist()
        })

    return log_entries


def evaluate_performance(log_entries, final_ref):
    """Calculate control performance metrics."""
    n = len(log_entries[0]["tensions"])
    tensions_arr = np.array([e["tensions"] for e in log_entries])
    refs_arr = np.array([e["references"][:n] for e in log_entries])
    time_arr = np.array([e["time"] for e in log_entries])

    abs_errors = np.abs(tensions_arr - refs_arr)

    # Steady-state error: mean error over last 20%
    tail_len = int(len(tensions_arr) * 0.2)
    sse = float(np.mean(abs_errors[-tail_len:]))

    # Settling time: section 2 (index 1) error within 5% of step magnitude
    step_mag = np.abs(final_ref[1] - 25.0)
    threshold = 0.05 * step_mag
    settle_t = 0.0
    for idx in range(len(time_arr) - 1, -1, -1):
        if abs_errors[idx, 1] > threshold:
            settle_t = time_arr[min(idx + 1, len(time_arr) - 1)] - time_arr[0]
            break

    return {
        "steady_state_error": sse,
        "settling_time": float(settle_t),
        "max_tension": float(np.max(tensions_arr)),
        "min_tension": float(np.min(tensions_arr))
    }


def main():
    print("=== R2R MPC Control - 4-Section Variant ===\n")

    sim = R2RSimulator()
    print(f"System config: {sim.get_params()}")

    # Step 1: Controller design
    print("\nStep 1: Building MPC controller...")
    ctrl = setup_controller(sim)
    with open("controller_params.json", "w") as fout:
        json.dump(ctrl, fout, indent=2)
    print(f"  Horizon: {ctrl['horizon_N']}")

    # Step 2: Closed-loop run
    print("\nStep 2: Executing closed-loop control...")
    entries = execute_control(sim, ctrl, sim_duration=5.1)
    with open("control_log.json", "w") as fout:
        json.dump({
            "phase": "control",
            "dt": 0.01,
            "data": entries
        }, fout, indent=2)
    print(f"  Recorded {len(entries)} timesteps")

    # Step 3: Metrics
    print("\nStep 3: Evaluating performance...")
    ref_final, _ = sim.get_reference(499)
    perf = evaluate_performance(entries, ref_final)
    with open("metrics.json", "w") as fout:
        json.dump(perf, fout, indent=2)

    print(f"  Steady-state error: {perf['steady_state_error']:.3f} N")
    print(f"  Settling time: {perf['settling_time']:.2f} s")
    print(f"  Max tension: {perf['max_tension']:.1f} N")
    print(f"  Min tension: {perf['min_tension']:.1f} N")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
EOF

echo "Oracle solution completed successfully."
