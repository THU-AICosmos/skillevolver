#!/bin/bash

# Install GaMMA for seismic event association
pip install git+https://github.com/AI4EPS/GaMMA.git@f6b1ac7680f50bcc7d5d3928361ba02a7df0f523

python3 << 'EOF'
import os
import numpy as np
import pandas as pd
import obspy
import seisbench.models as sbm
from pyproj import Proj
from gamma.utils import association, estimate_eps

# --- Configuration ---
CENTER_LON = -117.504
CENTER_LAT = 35.705
RADIUS_DEG = 0.5
DEPTH_RANGE = (0, 30)
TIME_WINDOW = ("2019-07-04T19:00:00", "2019-07-04T20:00:00")
OUTPUT_PATH = "/root/event_catalog.csv"

# Velocity model
VP = 6.0  # km/s
VS = VP / 1.75

# --- Step 1: Phase picking with PhaseNet ---
print("Loading waveforms...")
stream = obspy.read("/root/data/wave.mseed")
print(f"Loaded {len(stream)} traces")

print("Running PhaseNet phase picker...")
model = sbm.PhaseNet.from_pretrained("instance")
model.to_preferred_device(verbose=True)
detections = model.classify(stream, batch_size=256).picks

picks_list = [
    {
        "id": det.trace_id,
        "timestamp": det.peak_time.datetime,
        "prob": det.peak_value,
        "type": det.phase.lower(),
    }
    for det in detections
]
picks_df = pd.DataFrame(picks_list)
print(f"Detected {len(picks_df)} phase arrivals")

# --- Step 2: Load and prepare station metadata ---
stations_df = pd.read_csv("/root/data/stations.csv", na_filter=False)
stations_df["id"] = stations_df.apply(
    lambda r: f"{r['network']}.{r['station']}.", axis=1
)
stations_df = (
    stations_df.groupby("id")
    .agg(lambda grp: grp.iloc[0] if len(set(grp)) == 1 else sorted(list(grp)))
    .reset_index()
)

projection = Proj(f"+proj=aeqd +lon_0={CENTER_LON} +lat_0={CENTER_LAT} +units=km")
stations_df[["x(km)", "y(km)"]] = stations_df.apply(
    lambda r: pd.Series(projection(longitude=r.longitude, latitude=r.latitude)),
    axis=1,
)
stations_df["z(km)"] = stations_df["elevation_m"].apply(lambda e: -e / 1e3)

# --- Step 3: GaMMA association ---
xmin, ymin = projection(CENTER_LON - RADIUS_DEG, CENTER_LAT - RADIUS_DEG)
xmax, ymax = projection(CENTER_LON + RADIUS_DEG, CENTER_LAT + RADIUS_DEG)

gamma_config = {
    "longitude0": CENTER_LON,
    "latitude0": CENTER_LAT,
    "maxradius_degree": RADIUS_DEG,
    "starttime": TIME_WINDOW[0],
    "endtime": TIME_WINDOW[1],
    "use_dbscan": True,
    "use_amplitude": False,
    "method": "BGMM",
    "oversample_factor": 5,
    "vel": {"p": VP, "s": VS},
    "dims": ["x(km)", "y(km)", "z(km)"],
    "x(km)": (xmin, xmax),
    "y(km)": (ymin, ymax),
    "z(km)": (DEPTH_RANGE[0], DEPTH_RANGE[1]),
    "bfgs_bounds": (
        (xmin - 1, xmax + 1),
        (ymin - 1, ymax + 1),
        (0, DEPTH_RANGE[1] + 1),
        (None, None),
    ),
    "dbscan_eps": estimate_eps(stations_df, VP),
    "dbscan_min_samples": 3,
    "min_picks_per_eq": 5,
    "max_sigma11": 2.0,
    "max_sigma22": 1.0,
    "max_sigma12": 1.0,
}

print("Running GaMMA association...")
picks_df.drop(columns=["event_index"], inplace=True, errors="ignore")
events, assignments = association(picks_df, stations_df, gamma_config, 0, "BGMM")
print(f"Associated {len(events)} events")

if len(events) > 0:
    events_df = pd.DataFrame(events)
    events_df[["longitude", "latitude"]] = events_df.apply(
        lambda r: pd.Series(
            projection(longitude=r["x(km)"], latitude=r["y(km)"], inverse=True)
        ),
        axis=1,
    )
    events_df["depth_km"] = events_df["z(km)"]
    events_df.sort_values("time", inplace=True)
    events_df.to_csv(
        OUTPUT_PATH,
        index=False,
        float_format="%.3f",
        date_format="%Y-%m-%dT%H:%M:%S.%f",
    )
    print(f"Catalog saved to {OUTPUT_PATH}")
else:
    pd.DataFrame(columns=["time"]).to_csv(OUTPUT_PATH, index=False)
    print("No events detected!")

EOF
