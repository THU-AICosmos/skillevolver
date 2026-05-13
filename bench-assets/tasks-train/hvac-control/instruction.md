You need to implement a temperature controller for an industrial curing oven to maintain a temperature of 65.0C. The performance targets are: steady-state error <0.3C, settling time <180s, overshoot <8%, control duration >=200s, max temperature <85C. Also consider the constraints: Initial temperature ~25.0C (+/-3C sensor noise), heating element power 0-100%. Simulator environment is oven_simulator.py. You can use that to get initial temperature and doing some follow work.


Run a characterization test to profile the oven dynamics (need at least 40 seconds of data with 25+ data points), result in step_response_log.json. Then, estimate the system parameters from your characterization data, result in system_params.json. Then, calculate controller gains using estimated parameters, result in controller_config.json. Finally, run the closed-loop control to bring the oven to 65.0C, result in regulation_log.json and performance.json.


Examples output format:
step_response_log.json:
{
  "phase": "characterization",
  "element_power_test": 60.0,
  "data": [
    {"time": 0.0, "temperature": 25.0, "element_power": 0.0},
    {"time": 0.25, "temperature": 25.2, "element_power": 60.0}
  ]
}

system_params.json:
{
  "K": 0.5,
  "tau": 55.0,
  "r_squared": 0.92,
  "fitting_error": 0.15
}


controller_config.json:
{
  "Kp": 10.0,
  "Ki": 0.15,
  "Kd": 0.0,
  "lambda": 55.0
}


regulation_log.json:
{
  "phase": "regulation",
  "target": 65.0,
  "data": [
    {"time": 40.0, "temperature": 30.5, "target": 65.0, "element_power": 80.0, "error": 34.5}
  ]
}


performance.json:
{
  "rise_time": 50.0,
  "overshoot": 0.03,
  "settling_time": 110.0,
  "steady_state_error": 0.1,
  "max_temp": 66.2
}
