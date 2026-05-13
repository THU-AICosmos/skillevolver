You are given a collection of 100 seismic waveform recordings stored as `.npz` files under `/root/data/`. Your goal is to detect when earthquake waves arrive at each recording station.

Specifically, you need to identify the sample indices where primary (P) and secondary (S) waves first appear in each waveform trace. Each `.npz` file contains:
- `data`: a numpy array of shape (12000, 3) representing 3-component seismic data
- `dt`: the time interval between consecutive samples (in seconds)
- `channels`: a comma-separated string of channel identifiers (e.g., "DPE,DPN,DPZ")
Additional metadata fields may be present and can optionally be used.

Workflow:
1. Read each `.npz` file from `/root/data/` and prepare the waveform for analysis.
2. Apply a seismic phase detection method to determine the sample index of P-wave and S-wave arrivals. A trace may yield zero, one, or multiple picks per phase type.
3. Save all detected arrivals to `/root/results.csv` with the following columns:
    - `file_name`: the `.npz` filename
    - `phase`: either "P" or "S"
    - `pick_idx`: the integer sample index of the detected arrival

Evaluation criteria:
Picks are matched against expert-labeled ground truth using a tolerance window of 0.1 seconds (convertible to sample count via the sampling rate). Your solution will be evaluated on F1 score: P-wave F1 must be >= 0.7 and S-wave F1 must be >= 0.6. Choose an approach that maximizes these metrics.
