#!/bin/bash
set -e

pip install --no-cache-dir seisbench==0.10.2

python3 << 'PYEOF'
import numpy as np
import pandas as pd
import obspy
import seisbench.models as sbm
from obspy import Stream, Trace, UTCDateTime
from pathlib import Path
from glob import glob

# ---- Configuration ----
DATA_DIR = Path("/root/data")
OUTPUT_PATH = Path("/root/wave_detections.csv")
SCALE_FACTOR = 1e10

# ---- Helper: build ObsPy stream from npz ----
def npz_to_stream(npz_path):
    d = np.load(npz_path, allow_pickle=False)
    for key in ("data", "dt", "start_time", "network", "station", "channels"):
        if key not in d:
            return None

    waveform = d["data"] * SCALE_FACTOR
    sr = 1.0 / float(d["dt"])
    ch_str = str(d["channels"])
    ch_list = ch_str.split(",") if "," in ch_str else [f"HH{c}" for c in "ENZ"]

    try:
        t0 = UTCDateTime(str(d["start_time"]))
    except Exception:
        t0 = UTCDateTime(0)

    st = Stream()
    for idx, ch_name in enumerate(ch_list):
        if idx >= waveform.shape[1]:
            break
        tr = Trace(data=waveform[:, idx].astype(np.float64))
        tr.stats.network = str(d["network"])
        tr.stats.station = str(d["station"])
        tr.stats.channel = ch_name if len(ch_name) >= 2 else f"HH{ch_name}"
        tr.stats.sampling_rate = sr
        tr.stats.starttime = t0
        st.append(tr)
    return st

# ---- Load all data ----
npz_files = sorted(glob(str(DATA_DIR / "*.npz")))
streams = {}
for fpath in npz_files:
    fname = Path(fpath).name
    st = npz_to_stream(fpath)
    if st is not None:
        streams[fname] = st
        print(f"Loaded {fname}")

print(f"Total loaded: {len(streams)}")

# ---- Load model ----
picker = sbm.PhaseNet.from_pretrained("original")
picker.to_preferred_device()

# ---- Run detection ----
detections = []
for fname, st in streams.items():
    sr = st[0].stats.sampling_rate
    t0 = st[0].stats.starttime
    try:
        result = picker.classify(st)
        for pk in result.picks:
            sample_idx = int((pk.peak_time - t0) * sr)
            detections.append({
                "file_name": fname,
                "phase": pk.phase,
                "pick_idx": sample_idx,
            })
    except Exception as exc:
        print(f"Error on {fname}: {exc}")

# ---- Save output ----
pd.DataFrame(detections).to_csv(OUTPUT_PATH, index=False)
print(f"Wrote {len(detections)} detections to {OUTPUT_PATH}")
PYEOF
