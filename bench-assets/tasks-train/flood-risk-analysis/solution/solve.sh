#!/bin/bash
set -e

python3 <<'PYCODE'
"""Wisconsin flood-stage exceedance detector.

Pulls candidate USGS sites from a text manifest, joins each against the
NWS gauge inventory to recover its flood stage, then queries USGS IV
gage-height (parameter 00065) for the analysis window and counts how many
calendar days the daily peak met or exceeded the published flood stage.
"""

import csv
import io
import os
import sys
import urllib.request
from pathlib import Path

import pandas as pd
from dataretrieval import nwis

SITES_FILE = Path("/root/data/wisconsin_stations.txt")
OUTPUT_FILE = Path("/root/output/flood_results.csv")
NWS_INVENTORY_URL = (
    "https://water.noaa.gov/resources/downloads/reports/nwps_all_gauges_report.csv"
)
GAGE_HEIGHT_PARAM = "00065"
WINDOW_START = "2025-04-22"
WINDOW_END = "2025-04-28"


def load_site_manifest(path: Path) -> list[str]:
    sites: list[str] = []
    with path.open() as fh:
        for raw in fh:
            sid = raw.strip()
            if sid:
                sites.append(sid)
    return sites


def fetch_flood_stage_lookup(target_sites: set[str]) -> dict[str, float]:
    """Return {usgs_id: flood_stage_ft} restricted to target_sites."""
    print(f"Fetching NWS gauge inventory from {NWS_INVENTORY_URL} ...")
    with urllib.request.urlopen(NWS_INVENTORY_URL) as resp:
        payload = resp.read().decode("utf-8")

    csv_reader = csv.reader(io.StringIO(payload))
    header_row = next(csv_reader)
    # NWS report occasionally adds trailing metadata columns that don't exist
    # in every data row; normalize both sides to the narrower width.
    body_rows = [row for row in csv_reader]
    min_width = min([len(header_row)] + [len(r) for r in body_rows]) if body_rows else len(header_row)
    inventory = pd.DataFrame(
        [row[:min_width] for row in body_rows],
        columns=header_row[:min_width],
    )

    flood_col = pd.to_numeric(inventory["flood stage"], errors="coerce")
    inventory = inventory.assign(_flood_ft=flood_col)

    lookup: dict[str, float] = {}
    for _, record in inventory.iterrows():
        sid = str(record["usgs id"]).strip()
        if sid in target_sites and pd.notna(record["_flood_ft"]):
            lookup[sid] = float(record["_flood_ft"])
    return lookup


def daily_peak_series(site_id: str) -> pd.Series | None:
    """Return per-day max gage-height series for a site, or None on miss."""
    try:
        frame, _ = nwis.get_iv(
            sites=site_id,
            start=WINDOW_START,
            end=WINDOW_END,
            parameterCd=GAGE_HEIGHT_PARAM,
        )
    except Exception as exc:  # network / no-data / parse error
        print(f"  [{site_id}] fetch failed: {exc}")
        return None

    if frame is None or len(frame) == 0:
        return None

    cols = [c for c in frame.columns
            if GAGE_HEIGHT_PARAM in str(c) and "_cd" not in str(c)]
    if not cols:
        return None
    return frame[cols[0]].resample("D").max()


def count_exceedance_days(series: pd.Series, threshold: float) -> int:
    return int((series >= threshold).sum())


def write_output(rows: list[tuple[str, int]], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["station_id", "flood_days"])
        for sid, days in rows:
            writer.writerow([sid, days])


def main() -> int:
    candidates = load_site_manifest(SITES_FILE)
    print(f"Sites in manifest: {len(candidates)}")

    flood_stage = fetch_flood_stage_lookup(set(candidates))
    print(f"Sites with NWS flood stage published: {len(flood_stage)}")

    flagged: list[tuple[str, int]] = []
    for sid, threshold_ft in flood_stage.items():
        series = daily_peak_series(sid)
        if series is None:
            continue
        days = count_exceedance_days(series, threshold_ft)
        if days > 0:
            flagged.append((sid, days))

    flagged.sort(key=lambda pair: pair[1], reverse=True)
    print(f"Sites with >=1 flood day in window: {len(flagged)}")
    for sid, days in flagged:
        print(f"  {sid}: {days} day(s)")

    write_output(flagged, OUTPUT_FILE)
    print(f"Wrote {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
PYCODE
