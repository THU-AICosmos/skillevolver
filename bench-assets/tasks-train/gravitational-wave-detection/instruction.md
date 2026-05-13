You are tasked with characterizing a gravitational wave signal buried in noisy detector data. Your goal is to identify the best-matching waveform template and determine the individual component masses of the binary system.

The detector data is stored at `/root/data/PyCBC_T2_2.gwf` under the channel `H1:TEST-STRAIN`. You should condition this raw strain data (highpass filtering and downsampling) and then use matched filtering to search for the best-fitting template.

Perform a grid search using the following two waveform approximants: "IMRPhenomD" and "TaylorT4". For each approximant, scan over the component masses mass1 and mass2 from 15 to 35 solar masses in integer steps (with the convention mass1 >= mass2). For each approximant, identify the template with the highest signal-to-noise ratio (SNR).

Save your results to `/root/signal_analysis.csv` with the following columns:

```csv
waveform_model,peak_snr,mass1,mass2
```

Where:
- `waveform_model`: The approximant name ("IMRPhenomD" or "TaylorT4")
- `peak_snr`: The peak signal-to-noise ratio achieved by the best template
- `mass1`: The primary mass (in solar masses) of the best-matching template
- `mass2`: The secondary mass (in solar masses) of the best-matching template

The output should contain exactly two rows, one for each waveform model.
