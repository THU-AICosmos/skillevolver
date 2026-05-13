"""Generate a synthetic Kepler-like light curve with an injected transit signal."""
import numpy as np

np.random.seed(42)

# Time baseline: ~90 days of Kepler-like observations (long cadence ~30 min)
# with some gaps
t_start = 54953.0  # BJD - 2400000 (Kepler-like epoch)
cadence = 30.0 / (24 * 60)  # 30 minutes in days
n_total = 4500  # ~93 days of data

time_full = t_start + np.arange(n_total) * cadence

# Create gaps (data downlink, safe modes)
gap_mask = np.ones(n_total, dtype=bool)
# Gap 1: days 20-22
gap_mask[(time_full - t_start > 20) & (time_full - t_start < 22)] = False
# Gap 2: days 45-48
gap_mask[(time_full - t_start > 45) & (time_full - t_start < 48)] = False
# Gap 3: days 70-71
gap_mask[(time_full - t_start > 70) & (time_full - t_start < 71)] = False

time = time_full[gap_mask]
n_points = len(time)

# === Stellar variability (rotational modulation) ===
# Star rotation period ~8.5 days, with evolving spots
rot_period = 8.5
phase_rot = 2 * np.pi * (time - t_start) / rot_period
# Multi-harmonic stellar variability
stellar_var = (0.008 * np.sin(phase_rot + 0.3) +
               0.005 * np.sin(2 * phase_rot + 1.2) +
               0.003 * np.cos(3 * phase_rot + 0.7) +
               0.002 * np.sin(phase_rot / 2.3 + 0.5))  # slow drift

# Evolving spot amplitude
envelope = 1.0 + 0.15 * np.sin(2 * np.pi * (time - t_start) / 40.0)
stellar_var *= envelope

# === Planet transit signal ===
# Planet period: 3.24176 days, depth ~0.0025 (2500 ppm), duration ~2.5 hours
planet_period = 3.24176
transit_depth = 0.0025
transit_duration = 2.5 / 24.0  # hours to days
t0 = t_start + 1.5  # first transit time

# Simple box-shaped transit
phase = ((time - t0) % planet_period) / planet_period
# Center phase at 0
phase[phase > 0.5] -= 1.0
half_dur_phase = (transit_duration / 2.0) / planet_period
in_transit = np.abs(phase) < half_dur_phase

transit_signal = np.ones(n_points)
transit_signal[in_transit] -= transit_depth

# === Combine flux ===
flux_clean = (1.0 + stellar_var) * transit_signal

# === Add noise ===
base_noise = 0.0006  # ~600 ppm noise
noise_level = base_noise * (1 + 0.2 * np.random.rand(n_points))  # slightly varying noise
flux_noise = np.random.normal(0, noise_level)
flux = flux_clean + flux_noise

# === Quality flags ===
# 0 = good, 1 = suspect, 2 = bad
quality = np.zeros(n_points, dtype=int)
# Randomly mark ~3% as suspect (1) and ~1% as bad (2)
bad_idx = np.random.choice(n_points, size=int(0.01 * n_points), replace=False)
suspect_idx = np.random.choice(n_points, size=int(0.03 * n_points), replace=False)
quality[suspect_idx] = 1
quality[bad_idx] = 2

# Add some outliers to bad-quality points
flux[bad_idx] += np.random.normal(0, 0.01, size=len(bad_idx))

# Add a few random cosmic ray outliers to otherwise good data (they should be sigma-clipped)
cosmic_idx = np.random.choice(np.where(quality == 0)[0], size=15, replace=False)
flux[cosmic_idx] += np.random.choice([-1, 1], size=15) * np.random.uniform(0.005, 0.02, size=15)

# === Write CSV file ===
output_path = "/home/zhanggenrui/workplace/self-evolving-skills/Benchmarks/skillsbench/tasks-train/exoplanet-detection-period/environment/data/kepler_lightcurve.csv"
with open(output_path, 'w') as f:
    f.write("bjd,relative_flux,flux_err,quality_flag\n")
    for i in range(n_points):
        f.write(f"{time[i]:.8f},{flux[i]:.10f},{noise_level[i]:.10f},{quality[i]}\n")

print(f"Generated {n_points} data points")
print(f"Injected planet period: {planet_period} days")
print(f"Transit depth: {transit_depth}")
print(f"Number of expected transits: {(time[-1]-time[0])/planet_period:.1f}")

# Verify transit count
n_transits = int((time[-1] - t0) / planet_period)
print(f"Number of full transits: {n_transits}")
