import os
import subprocess
import numpy as np
import pandas as pd
from datetime import datetime
from netCDF4 import Dataset
import pytest

LAKE_DEPTH = 15
SIM_FOLDER = '/root'


def extract_sim_profiles(nc_path):
    nc = Dataset(nc_path, 'r')
    time_var = nc.variables['time'][:]
    z_var = nc.variables['z'][:]
    temp_var = nc.variables['temp'][:]
    ref_date = datetime(2010, 1, 1, 12, 0, 0)
    rows = []
    for ti in range(len(time_var)):
        hrs = float(time_var[ti])
        tstamp = pd.Timestamp(ref_date) + pd.Timedelta(hours=hrs)
        layer_heights = z_var[ti, :, 0, 0]
        layer_temps = temp_var[ti, :, 0, 0]
        for li in range(len(layer_heights)):
            hv = layer_heights[li]
            tv = layer_temps[li]
            if not np.ma.is_masked(hv) and not np.ma.is_masked(tv):
                dep = LAKE_DEPTH - float(hv)
                if 0 <= dep <= LAKE_DEPTH:
                    rows.append({
                        'datetime': tstamp,
                        'depth': round(dep),
                        'temp_sim': float(tv)
                    })
    nc.close()
    df = pd.DataFrame(rows)
    df = df.groupby(['datetime', 'depth']).agg({'temp_sim': 'mean'}).reset_index()
    return df


def load_field_obs(csv_path):
    df = pd.read_csv(csv_path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['depth'] = df['depth'].round().astype(int)
    df = df.rename(columns={'temp': 'temp_obs'})
    return df[['datetime', 'depth', 'temp_obs']]


def compute_rmse(sim_df, obs_df):
    combined = pd.merge(obs_df, sim_df, on=['datetime', 'depth'], how='inner')
    if len(combined) == 0:
        return 999.0
    return np.sqrt(np.mean((combined['temp_sim'] - combined['temp_obs'])**2))


class TestGLMLakeWaban:
    """Test cases for GLM Lake Waban calibration task."""

    def test_glm_executes(self):
        """Verify that GLM runs without errors using agent's parameters."""
        proc = subprocess.run(['glm'], cwd=SIM_FOLDER, capture_output=True, text=True)
        assert proc.returncode == 0, f"GLM execution failed: {proc.stderr}"

    def test_netcdf_output_present(self):
        """Verify that the NetCDF output file was generated."""
        nc_file = os.path.join(SIM_FOLDER, 'output', 'output.nc')
        assert os.path.exists(nc_file), "output.nc was not generated"

    def test_rmse_below_threshold(self):
        """Verify that RMSE < 2.5C."""
        nc_file = os.path.join(SIM_FOLDER, 'output', 'output.nc')
        obs_file = os.path.join(SIM_FOLDER, 'field_observations.csv')

        sim_profiles = extract_sim_profiles(nc_file)
        field_obs = load_field_obs(obs_file)
        rmse_val = compute_rmse(sim_profiles, field_obs)

        assert rmse_val < 2.5, f"RMSE {rmse_val:.2f}C >= 2.5C threshold"
