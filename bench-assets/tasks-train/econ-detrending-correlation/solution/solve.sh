#!/bin/bash
set -e

python3 << 'EOF'
import pandas as pd
import numpy as np
from statsmodels.tsa.filters.hp_filter import hpfilter
import os

def compute_business_cycle_correlation():
    """Compute correlation between HP-filtered government spending and exports."""

    # Determine data file locations
    root_dir = "/root"
    if not os.path.exists(os.path.join(root_dir, "government_spending_annual.csv")):
        root_dir = "."

    # Read the three data sources
    spending_data = pd.read_csv(os.path.join(root_dir, "government_spending_annual.csv"))
    trade_data = pd.read_csv(os.path.join(root_dir, "exports_annual.csv"))
    deflator_data = pd.read_excel(os.path.join(root_dir, "ppi_index.xlsx"))

    # Extract relevant columns
    yr_range = (spending_data["Year"] >= 1965) & (spending_data["Year"] <= 2019)
    spending_series = spending_data.loc[yr_range, ["Year", "Total_Government_Spending"]].copy()

    yr_range_t = (trade_data["Year"] >= 1965) & (trade_data["Year"] <= 2019)
    trade_series = trade_data.loc[yr_range_t, ["Year", "Total_Exports"]].copy()

    yr_range_d = (deflator_data["Year"] >= 1965) & (deflator_data["Year"] <= 2019)
    price_index = deflator_data.loc[yr_range_d, ["Year", "PPI"]].copy()

    # Merge all series on Year
    merged = spending_series.merge(trade_series, on="Year").merge(price_index, on="Year")
    merged = merged.sort_values("Year").reset_index(drop=True)

    expected_count = 2019 - 1965 + 1
    if len(merged) != expected_count:
        print(f"Warning: Expected {expected_count} observations, found {len(merged)}")

    # Deflate nominal to real using PPI
    real_spending = merged["Total_Government_Spending"] / merged["PPI"]
    real_exports = merged["Total_Exports"] / merged["PPI"]

    # Take natural logarithm
    log_spending = np.log(real_spending)
    log_exports = np.log(real_exports)

    # Apply Hodrick-Prescott filter with lambda=100 (annual)
    cyclical_spending, _ = hpfilter(log_spending, lamb=100)
    cyclical_exports, _ = hpfilter(log_exports, lamb=100)

    # Pearson correlation of cyclical components
    rho = np.corrcoef(cyclical_spending, cyclical_exports)[0, 1]
    return rho


if __name__ == "__main__":
    try:
        rho = compute_business_cycle_correlation()
        print(f"Business cycle correlation (Gov Spending vs Exports): {rho:.5f}")

        out_file = "/root/result.txt"
        if not os.path.exists("/root"):
            out_file = "result.txt"

        with open(out_file, "w") as fh:
            fh.write(f"{rho:.5f}")

    except Exception as exc:
        print(f"Error: {exc}")
        raise
EOF
