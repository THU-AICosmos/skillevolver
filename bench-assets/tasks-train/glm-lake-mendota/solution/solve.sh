#!/bin/bash
set -e
python3 -u << 'PYTHON'
import subprocess
import os
import re
import numpy as np
import pandas as pd
from datetime import datetime
from netCDF4 import Dataset
from scipy.optimize import differential_evolution

WORK_DIR = '/root'
MAX_DEPTH = 15
RMSE_GOAL = 2.0
field_data = None
eval_count = 0
top_rmse = 999.0
top_config = None


class StopOptimization(Exception):
    pass


def update_namelist(filepath, param_dict):
    """Write parameter values into the GLM namelist file."""
    with open(filepath, 'r') as fh:
        text = fh.read()
    for key, val in param_dict.items():
        regex = rf"({key}\s*=\s*)[\d\.\-e]+"
        text = re.sub(regex, rf"\g<1>{val}", text)
    with open(filepath, 'w') as fh:
        fh.write(text)


def execute_glm():
    """Run the GLM executable and return success status."""
    proc = subprocess.run(['glm'], cwd=WORK_DIR, capture_output=True, text=True)
    return proc.returncode == 0


def parse_netcdf_output(nc_file):
    """Read GLM NetCDF output and return a DataFrame of simulated temperatures."""
    ds = Dataset(nc_file, 'r')
    t_hours = ds.variables['time'][:]
    z_vals = ds.variables['z'][:]
    t_vals = ds.variables['temp'][:]
    origin = datetime(2010, 1, 1, 12, 0, 0)

    data_rows = []
    for step in range(len(t_hours)):
        ts = pd.Timestamp(origin) + pd.Timedelta(hours=float(t_hours[step]))
        layer_z = z_vals[step, :, 0, 0]
        layer_t = t_vals[step, :, 0, 0]
        for k in range(len(layer_z)):
            zv = layer_z[k]
            tv = layer_t[k]
            if not np.ma.is_masked(zv) and not np.ma.is_masked(tv):
                d = MAX_DEPTH - float(zv)
                if 0 <= d <= MAX_DEPTH:
                    data_rows.append({'datetime': ts, 'depth': round(d), 'temp_sim': float(tv)})
    ds.close()
    result = pd.DataFrame(data_rows)
    result = result.groupby(['datetime', 'depth']).agg({'temp_sim': 'mean'}).reset_index()
    return result


def load_observations(csv_file):
    """Load field observation data."""
    obs = pd.read_csv(csv_file)
    obs['datetime'] = pd.to_datetime(obs['datetime'])
    obs['depth'] = obs['depth'].round().astype(int)
    obs = obs.rename(columns={'temp': 'temp_obs'})
    return obs[['datetime', 'depth', 'temp_obs']]


def eval_rmse(sim_data, obs_data):
    """Compute RMSE between simulated and observed temperatures."""
    joined = pd.merge(obs_data, sim_data, on=['datetime', 'depth'], how='inner')
    if len(joined) == 0:
        return 999.0
    return np.sqrt(np.mean((joined['temp_sim'] - joined['temp_obs'])**2))


def cost_function(params_vec):
    """Objective function for optimization."""
    global eval_count, top_rmse, top_config
    eval_count += 1

    kw_val, mix_hyp_val, wf_val, lwf_val, ch_val = params_vec
    cfg = {
        'Kw': round(kw_val, 4),
        'coef_mix_hyp': round(mix_hyp_val, 4),
        'wind_factor': round(wf_val, 4),
        'lw_factor': round(lwf_val, 4),
        'ch': round(ch_val, 6)
    }
    update_namelist(os.path.join(WORK_DIR, 'glm3.nml'), cfg)

    if not execute_glm():
        return 999.0

    nc_out = os.path.join(WORK_DIR, 'output', 'output.nc')
    sim = parse_netcdf_output(nc_out)
    error = eval_rmse(sim, field_data)

    print(f"  [{eval_count:3d}] Kw={kw_val:.3f} hyp={mix_hyp_val:.3f} wf={wf_val:.3f} lw={lwf_val:.3f} ch={ch_val:.5f} => RMSE={error:.3f}")

    if error < top_rmse:
        top_rmse = error
        top_config = cfg.copy()

    if error < RMSE_GOAL:
        raise StopOptimization()

    return error


def calibrate():
    """Main calibration routine using differential evolution."""
    global field_data, top_config
    print("=" * 55)
    print("Lake Waban GLM Calibration")
    print("=" * 55)

    field_data = load_observations(os.path.join(WORK_DIR, 'field_observations.csv'))
    print(f"Loaded {len(field_data)} field observations")

    bounds = [
        (0.15, 0.7),    # Kw
        (0.2, 0.7),     # coef_mix_hyp
        (0.7, 1.3),     # wind_factor
        (0.8, 1.2),     # lw_factor
        (0.0006, 0.002) # ch
    ]

    print("\nRunning parameter optimization...")
    print("-" * 55)

    try:
        differential_evolution(
            cost_function,
            bounds,
            seed=7,
            maxiter=15,
            popsize=5,
            tol=0.05,
            mutation=(0.5, 1.0),
            recombination=0.7
        )
    except StopOptimization:
        print(f"\n*** Reached target: RMSE < {RMSE_GOAL} ***")

    if top_config:
        update_namelist(os.path.join(WORK_DIR, 'glm3.nml'), top_config)
        execute_glm()

    print("\n" + "=" * 55)
    print("Done!")
    print("=" * 55)
    print(f"Best RMSE: {top_rmse:.3f} C")


if __name__ == '__main__':
    calibrate()
PYTHON
