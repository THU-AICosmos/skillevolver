You are provided with a lightcurve from a Kepler-like survey at `/root/data/kepler_lightcurve.csv`. The file is in CSV format with a header row and the following columns: `bjd` (Barycentric Julian Date), `relative_flux` (normalized flux), `flux_err` (flux uncertainty), `quality_flag` (0 = good, 1 = suspect, 2 = bad).

The lightcurve shows significant stellar variability from starspot modulation that obscures a transiting exoplanet signal. Your goal is to extract the orbital period of the hidden planet by performing the following analysis:

1. Load the CSV data and filter out bad-quality observations (keep only `quality_flag == 0`)
2. Remove outliers from the filtered data
3. Detrend the stellar variability (flatten the light curve) to reveal the transit signal
4. Use a period-finding algorithm (e.g., BLS or TLS) to determine the planet's orbital period

Write the orbital period to `/root/orbital_period.txt` in the following format:
- A single numerical value in days
- Round the value to 4 decimal places

Example: If you find a period of 4.12839 days, write:
```
4.1284
```
