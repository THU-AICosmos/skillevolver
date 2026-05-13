#!/usr/bin/env python3
"""
Gravitational Wave Signal Characterization

Characterize gravitational wave signals by performing matched filtering
with two waveform models (IMRPhenomD and TaylorT4) over a focused
mass parameter space, reporting the best-fit component masses.
"""

import pandas as pd
from pycbc.filter import highpass, matched_filter, resample_to_delta_t
from pycbc.frame import read_frame
from pycbc.psd import interpolate, inverse_spectrum_truncation
from pycbc.waveform import get_td_waveform


def load_and_condition_strain(filepath, channel):
    """Load detector strain data and apply conditioning."""
    raw = read_frame(filepath, channel)
    # Apply highpass filter and downsample
    filtered = resample_to_delta_t(highpass(raw, 15.0), 1.0 / 4096)
    # Crop edges to remove filter artifacts
    return filtered.crop(2, 2)


def estimate_psd(data):
    """Estimate power spectral density from conditioned data."""
    psd_raw = data.psd(4)
    psd_interp = interpolate(psd_raw, data.delta_f)
    return inverse_spectrum_truncation(
        psd_interp, int(4 * data.sample_rate), low_frequency_cutoff=15
    )


def search_templates(data, noise_psd, models, mass_lo, mass_hi):
    """
    Grid search over waveform models and component masses.
    Returns list of dicts with model, m1, m2, and peak SNR.
    """
    hits = []
    for model_name in models:
        for m1 in range(mass_lo, mass_hi + 1):
            for m2 in range(mass_lo, m1 + 1):
                try:
                    hp, _ = get_td_waveform(
                        approximant=model_name,
                        mass1=m1,
                        mass2=m2,
                        delta_t=data.delta_t,
                        f_lower=20,
                    )
                    hp.resize(len(data))
                    template = hp.cyclic_time_shift(hp.start_time)

                    snr_ts = matched_filter(
                        template, data, psd=noise_psd, low_frequency_cutoff=20
                    )
                    snr_ts = snr_ts.crop(4 + 4, 4)

                    peak_idx = abs(snr_ts).numpy().argmax()
                    peak_val = float(abs(snr_ts[peak_idx]))

                    hits.append({
                        "waveform_model": model_name,
                        "mass1": m1,
                        "mass2": m2,
                        "peak_snr": peak_val,
                    })
                except Exception:
                    continue
    return hits


def find_best_per_model(hits, models):
    """Select the highest-SNR template for each waveform model."""
    best = {}
    for h in hits:
        m = h["waveform_model"]
        if m not in best or h["peak_snr"] > best[m]["peak_snr"]:
            best[m] = h
    # Return ordered by model list
    return [best[m] for m in models if m in best]


def main():
    data_file = "/root/data/PyCBC_T2_2.gwf"
    channel = "H1:TEST-STRAIN"
    waveform_models = ["IMRPhenomD", "TaylorT4"]
    mass_lower = 15
    mass_upper = 35

    print("Loading and conditioning strain data...")
    conditioned = load_and_condition_strain(data_file, channel)

    print("Estimating PSD...")
    psd = estimate_psd(conditioned)

    print(f"Searching templates: models={waveform_models}, mass=[{mass_lower},{mass_upper}]")
    all_hits = search_templates(conditioned, psd, waveform_models, mass_lower, mass_upper)

    print(f"Total templates evaluated: {len(all_hits)}")
    best_results = find_best_per_model(all_hits, waveform_models)

    # Build output DataFrame
    output_df = pd.DataFrame(best_results)[["waveform_model", "peak_snr", "mass1", "mass2"]]
    output_df.to_csv("/root/signal_analysis.csv", index=False)

    print("\nResults written to /root/signal_analysis.csv")
    for _, row in output_df.iterrows():
        print(
            f"  {row['waveform_model']}: SNR={row['peak_snr']:.2f}, "
            f"m1={row['mass1']}, m2={row['mass2']}"
        )


if __name__ == "__main__":
    main()
