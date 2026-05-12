You have seismic waveform recordings stored at `/root/data/wave.mseed` and a station inventory at `/root/data/stations.csv`.

Your goal is to build an automated earthquake catalog by detecting and locating seismic events from the continuous waveform data.

The waveform data is in standard MSEED format.

Each row of the station inventory represents ONE channel of a seismic sensor, with the following columns:
1. `network`, `station`: identifiers of the seismic network and sensor
2. `channel`: channel code e.g. BHE
3. `longitude`, `latitude`: geographic coordinates of the sensor in degrees
4. `elevation_m`: sensor elevation in meters
5. `response`: instrument sensitivity

You should assume a uniform velocity model with `vp=6km/s` and `vs=vp/1.75` for wave propagation.

Steps:
1. Read the waveform recordings and the station inventory.
2. Apply a deep-learning seismic phase picker (available in SeisBench) to detect P-wave and S-wave arrivals across all stations.
3. Cluster the detected arrivals into coherent earthquake events using a phase association algorithm, and estimate each event's origin time.
4. Save the resulting earthquake catalog to `/root/earthquake_catalog.csv`. Each row must represent one detected earthquake. The file must contain a column named `event_time` with the origin time in ISO format (no timezone). Additional columns are allowed but will be ignored during evaluation.

Evaluation (reduced scope):
Your catalog will be compared to a human-reviewed reference catalog. An event is considered correctly detected if its origin time matches a reference event within 5 seconds. You need to achieve an F1 score >= 0.4 to pass. Additionally, your catalog must contain at least 50 detected events within the evaluation time window.
