You need to implement a Drone Altitude Hold Controller simulation that climbs to the set altitude (50m) when no obstacles are detected above, and automatically adjusts altitude to maintain a safe vertical gap when an obstacle is detected above. The targets are: altitude rise time <12s, altitude overshoot <5%, altitude steady-state error <1.0 m, gap steady-state error <3m, minimum gap >4m, control duration 120s. Also consider the constraints: initial altitude ~0 m, thrust limits [-6.0, 4.0] m/s^2, time margin 1.2s, minimum gap 8.0m, emergency TTC threshold 2.5s, timestep 0.1s. Data is available in drone_params.yaml(Drone specs and controller settings) and sensor_data.csv (1201 rows (t=0-120s) with columns: time, altitude, ref_altitude, gap, collected from real-world flight sensors).


First, create pid_controller.py to implement the PID controller. Then, create altitude_controller.py to implement the altitude control system and simulation.py to run the drone simulation. Next, tune the PID parameters for altitude and gap control, saving results in tuning_results.yaml. Finally, run 120s simulations, producing simulation_results.csv and flight_report.md.


Examples output format:

pid_controller.py:
Class: PIDController
Constructor: __init__(self, kp, ki, kd)
Methods: reset(), compute(error, dt) returns float

altitude_controller.py:
Class: AltitudeController
Constructor: __init__(self, config) where config is nested dict from drone_params.yaml (e.g., config['controller_settings']['set_altitude'])
Method: compute(altitude, ref_altitude, gap, dt) returns tuple (thrust_cmd, mode, gap_error)
Mode selection: 'climb' when ref_altitude is None, 'emergency_dive' when TTC < threshold, 'maintain' when obstacle present

simulation.py:
Read PID gains from tuning_results.yaml file at runtime.
Do not embed auto-tuning logic because gains should be loaded from the yaml file.
Uses sensor_data.csv for obstacle data (ref_altitude, gap).

tuning_results.yaml, kp in (0,10), ki in [0,5), kd in [0,5):
pid_altitude:
  kp: <value>
  ki: <value>
  kd: <value>
pid_gap:
  kp: <value>
  ki: <value>
  kd: <value>

simulation_results.csv:
(exactly 1201 rows, exact same column order)
time,altitude,thrust_cmd,mode,gap_error,gap,ttc
0.0,0.0,4.0,climb,,,
0.1,0.4,4.0,climb,,,
0.2,0.8,4.0,climb,,,
0.3,1.2,4.0,climb,,,
0.4,1.6,4.0,climb,,,
0.5,2.0,4.0,climb,,,
0.6,2.4,4.0,climb,,,

flight_report.md:
Include sections covering:
System design (altitude controller architecture, modes, safety features)
PID tuning methodology and final gains
Simulation results and performance metrics
