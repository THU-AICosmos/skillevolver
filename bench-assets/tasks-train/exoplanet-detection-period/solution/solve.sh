#!/bin/bash
set -e

python3 << 'EOF'
import numpy as np
import pandas as pd
import lightkurve as lk
import transitleastsquares as tls

# Load Kepler light curve CSV data
data_path = '/root/data/kepler_lightcurve.csv'
df = pd.read_csv(data_path)

# Extract columns
time = df['bjd'].values
flux = df['relative_flux'].values
flux_err = df['flux_err'].values
quality = df['quality_flag'].values

# Filter by quality flags (keep only flag == 0, good data)
good = quality == 0
time = time[good]
flux = flux[good]
flux_err = flux_err[good]

# Create light curve object
lc = lk.LightCurve(time=time, flux=flux, flux_err=flux_err)

# Remove outliers (sigma=3)
lc_clean, out_mask = lc.remove_outliers(sigma=3, return_mask=True)

# Flatten the lightcurve to remove stellar variability
lc_flat = lc_clean.flatten()

# Transit Least Squares search for exoplanet period
pg_tls = tls.transitleastsquares(
    lc_flat.time.value,
    lc_flat.flux.value,
    lc_flat.flux_err.value
)

# Initial search
out_tls = pg_tls.power(
    show_progress_bar=False,
    verbose=False
)

period = out_tls.period

# Refine the period with ±5% search range
min_period = 0.95 * period
max_period = 1.05 * period

pg_tls2 = tls.transitleastsquares(
    lc_flat.time.value,
    lc_flat.flux.value,
    lc_flat.flux_err.value
)

out_tls_refined = pg_tls2.power(
    period_min=min_period,
    period_max=max_period,
    show_progress_bar=False,
    verbose=False
)

period_final = out_tls_refined.period

# Write result to file
output_path = '/root/orbital_period.txt'
with open(output_path, 'w') as f:
    f.write(f"{period_final:.4f}\n")

print(f"Best-fit period: {period_final:.5f} days")
print(f"Written to {output_path}")
EOF
