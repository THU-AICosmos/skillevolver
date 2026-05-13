#!/bin/bash
set -e

python3 << 'PYEOF'
import os
import numpy as np
import pandas as pd
import obspy
import seisbench.models as sbm
from obspy import Stream, Trace, UTCDateTime
from pathlib import Path

DATA_DIR = Path("/root/data")
OUTPUT_PATH = Path("/root/results.csv")

# ---------- helpers ----------

def npz_to_stream(fpath):
    """Convert a single .npz file into an obspy Stream."""
    arr = np.load(fpath, allow_pickle=False)
    waveform = arr["data"].astype(np.float64) * 1e10
    sr = 1.0 / float(arr["dt"])
    chan_str = str(arr["channels"])
    chans = chan_str.split(",") if "," in chan_str else [f"HH{c}" for c in "ENZ"]
    try:
        t0 = UTCDateTime(str(arr["start_time"]))
    except Exception:
        t0 = UTCDateTime(0)
    st = Stream()
    for idx, ch in enumerate(chans):
        if idx >= waveform.shape[1]:
            break
        tr = Trace(data=waveform[:, idx])
        tr.stats.network = str(arr["network"])
        tr.stats.station = str(arr["station"])
        tr.stats.channel = ch if len(ch) >= 2 else f"HH{ch}"
        tr.stats.sampling_rate = sr
        tr.stats.starttime = t0
        st.append(tr)
    return st

# ---------- main pipeline ----------

print("Loading PhaseNet model …")
picker = sbm.PhaseNet.from_pretrained("original")
picker.to_preferred_device()

rows = []
npz_files = sorted(DATA_DIR.glob("*.npz"))
print(f"Processing {len(npz_files)} waveform files …")

for fpath in npz_files:
    fname = fpath.name
    try:
        stream = npz_to_stream(fpath)
    except Exception as exc:
        print(f"  SKIP {fname}: {exc}")
        continue

    sr = stream[0].stats.sampling_rate
    t0 = stream[0].stats.starttime

    try:
        result = picker.classify(stream)
        for pk in result.picks:
            idx = int((pk.peak_time - t0) * sr)
            rows.append({"file_name": fname, "phase": pk.phase, "pick_idx": idx})
    except Exception as exc:
        print(f"  ERROR {fname}: {exc}")

df = pd.DataFrame(rows, columns=["file_name", "phase", "pick_idx"])
df.to_csv(OUTPUT_PATH, index=False)
print(f"Wrote {len(df)} picks to {OUTPUT_PATH}")
PYEOF
