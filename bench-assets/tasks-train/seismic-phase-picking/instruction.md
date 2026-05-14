You are provided with 100 seismic waveform recordings stored as `.npz` files under `/root/data/`. Your goal is to detect the arrival indices of primary (P) and secondary (S) seismic waves in each recording.

Each `.npz` file contains at minimum:
- `data`: a numpy array of shape (12000, 3) representing seismogram samples across 3 channels
- `dt`: the time interval between consecutive samples (in seconds)
- `channels`: a string of comma-separated channel identifiers (e.g., "DPE,DPN,DPZ")

Additional metadata fields may exist and can be used if helpful.

Workflow:
1. Read each `.npz` file from `/root/data/` and prepare the waveform for analysis
2. Apply a seismic phase detection method to identify P-wave and S-wave arrival sample indices
3. You may detect zero, one, or multiple arrivals of each phase type per file
4. Save all detections to `/root/wave_detections.csv` with the following columns:
    - `file_name`: the name of the `.npz` file
    - `phase`: either "P" or "S"
    - `pick_idx`: the sample index of the detected arrival

Evaluation criteria:
Your detections will be compared against expert-labeled ground truth. A detection is considered correct if it falls within 0.1 seconds of the true arrival (convert this to sample tolerance using the sampling rate). The grading focuses on P-wave precision (must be >= 0.65) and S-wave recall (must be >= 0.45). Choose your approach accordingly.
