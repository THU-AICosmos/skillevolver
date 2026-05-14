You have seismic waveform recordings at `/root/data/wave.mseed` (MiniSEED format) and a station metadata file at `/root/data/stations.csv`.

Your goal is to build an automated seismic event detector: analyze the waveforms to detect individual earthquake occurrences and output a catalog of detected events.

The station CSV contains per-channel rows with columns:
- `network`, `station`: identifiers for the seismic network and station
- `channel`: instrument channel code (e.g., BHZ)
- `longitude`, `latitude`: geographic coordinates in degrees
- `elevation_m`: station elevation in meters
- `response`: instrument sensitivity

Use a 1D uniform velocity model with P-wave velocity `vp = 6 km/s` and S-wave velocity `vs = vp / 1.75`.

Workflow:
1. Read the waveforms and station metadata.
2. Apply a deep-learning seismic phase picker (e.g., from SeisBench) to detect P and S wave arrivals across all traces.
3. Associate the detected arrivals across stations to identify coherent earthquake events, producing event origin times.
4. Save the detected event catalog to `/root/event_catalog.csv`. The file must have a `time` column with event timestamps in ISO format (no timezone). Additional columns are allowed but ignored during evaluation.

Grading:
Your detected catalog will be compared against a reference catalog of known events. A detection is considered correct if it falls within 5 seconds of a reference event. You need to achieve a precision score above 0.5 to pass.
