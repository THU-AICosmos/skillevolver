#!/bin/bash
set -e

python3 << 'SOLVER'
import json
from datetime import datetime
import geopandas as gpd
from shapely.geometry import Point

# Input paths
ERUPTIONS_PATH = "/root/volcanic_eruptions_2023.json"
PLATES_PATH = "/root/PB2002_plates.json"
BOUNDS_PATH = "/root/PB2002_boundaries.json"
RESULT_PATH = "/root/result.json"

# Coordinate reference system for metric distances
PROJ_CRS = "EPSG:4087"


def parse_eruption_records(fpath):
    """Read volcanic eruption GeoJSON and return list of dicts."""
    print(f"Reading eruption records from {fpath} ...")
    with open(fpath, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    records = []
    for feat in raw["features"]:
        p = feat["properties"]
        c = feat["geometry"]["coordinates"]
        records.append({
            "event_id": feat["id"],
            "location": p["place"],
            "epoch_ms": p["time"],
            "vei": p["mag"],
            "lon": c[0],
            "lat": c[1],
            "depth_km": c[2],
        })
    print(f"  -> {len(records)} records loaded")
    return records


def run():
    records = parse_eruption_records(ERUPTIONS_PATH)

    # Build GeoDataFrame of eruptions
    pts = [Point(r["lon"], r["lat"]) for r in records]
    gdf_events = gpd.GeoDataFrame(records, geometry=pts, crs="EPSG:4326")

    # Load tectonic plate polygons and boundaries
    gdf_plates = gpd.read_file(PLATES_PATH)
    gdf_bounds = gpd.read_file(BOUNDS_PATH)

    # ---- Step 1: isolate Australian plate polygon ----
    print("Extracting Australian plate polygon ...")
    au_shape = gdf_plates[gdf_plates["PlateName"] == "Australia"].geometry.unary_union

    # ---- Step 2: keep only eruptions inside the AU plate ----
    print("Filtering eruptions within Australian plate ...")
    mask = gdf_events.within(au_shape)
    au_events = gdf_events[mask].copy()
    print(f"  -> {len(au_events)} eruptions fall inside the Australian plate")

    if au_events.empty:
        raise RuntimeError("No eruptions found inside the Australian plate!")

    # ---- Step 3: compute distance to AU boundaries ----
    print("Computing distances to AU plate boundaries ...")
    au_events_metric = au_events.to_crs(PROJ_CRS)

    au_boundary_lines = (
        gdf_bounds[gdf_bounds["Name"].str.contains("AU")]
        .to_crs(PROJ_CRS)
        .geometry.unary_union
    )
    au_events["dist_km"] = au_events_metric.geometry.distance(au_boundary_lines) / 1e3

    # ---- Step 4: pick the most isolated eruption ----
    most_isolated = au_events.nlargest(1, "dist_km").iloc[0]

    ts = datetime.utcfromtimestamp(most_isolated["epoch_ms"] / 1e3).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    output = {
        "event_id": most_isolated["event_id"],
        "location": most_isolated["location"],
        "timestamp": ts,
        "vei": most_isolated["vei"],
        "lat": most_isolated["lat"],
        "lon": most_isolated["lon"],
        "boundary_distance_km": round(most_isolated["dist_km"], 2),
    }

    print("\n=== Most isolated volcanic eruption in the Australian Plate ===")
    for k, v in output.items():
        print(f"  {k}: {v}")

    with open(RESULT_PATH, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)
    print(f"\nResult written to {RESULT_PATH}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"FATAL: {exc}")
        import traceback
        traceback.print_exc()
        exit(1)
SOLVER
