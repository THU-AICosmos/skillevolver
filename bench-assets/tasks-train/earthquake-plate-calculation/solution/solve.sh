#!/bin/bash
set -e

# Run the python solution
python3 << 'EOF'
import json
from datetime import datetime
import geopandas as gpd
from shapely.geometry import Point

# File path configuration
EARTHQUAKES_FILE = "/root/earthquakes_2024.json"
PLATES_POLY_FILE = "/root/PB2002_plates.json"
BOUNDARIES_FILE = "/root/PB2002_boundaries.json"
output_file = "/root/answer.json"

# Projection (metric)
METRIC_CRS = "EPSG:4087"


def load_earthquakes_from_file():
    """
    Load earthquake data from local file
    """
    print(f"Loading earthquake data from {EARTHQUAKES_FILE}...")

    with open(EARTHQUAKES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    earthquakes = []
    for feature in data["features"]:
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]

        earthquakes.append({
            "id": feature["id"],
            "place": props["place"],
            "time": props["time"],
            "mag": props["mag"],
            "longitude": coords[0],
            "latitude": coords[1],
            "depth": coords[2],
        })

    print(f"Successfully loaded {len(earthquakes)} earthquake records")
    return earthquakes


def main():
    print("Loading data...")

    # Load earthquake data from local file
    earthquakes = load_earthquakes_from_file()
    gdf_plates = gpd.read_file(PLATES_POLY_FILE)
    gdf_boundaries = gpd.read_file(BOUNDARIES_FILE)

    # Convert to GeoDataFrame
    geometry = [Point(eq["longitude"], eq["latitude"]) for eq in earthquakes]
    gdf_eq = gpd.GeoDataFrame(earthquakes, geometry=geometry, crs="EPSG:4326")

    # ================= Step 1: Identify North American Plate region =================
    print("Filtering North American Plate region...")
    na_poly = gdf_plates[gdf_plates["PlateName"] == "North America"].geometry.unary_union

    # ================= Step 2: Spatial filtering (keep only earthquakes inside NA Plate) =================
    print("Filtering earthquakes within the North American Plate...")
    is_in_na = gdf_eq.within(na_poly)
    na_quakes = gdf_eq[is_in_na].copy()

    print(
        f" -> Total of {len(gdf_eq)} earthquakes globally in 2024, {len(na_quakes)} occurred within the North American Plate."
    )

    if len(na_quakes) == 0:
        print("No earthquakes found within the North American Plate.")
        return

    # ================= Step 3: Compute centroid and distances =================
    print("Computing plate centroid and distances...")
    # Project to metric coordinate system for distance calculation
    na_quakes_proj = na_quakes.to_crs(METRIC_CRS)
    na_plate_proj = gdf_plates[gdf_plates["PlateName"] == "North America"].to_crs(METRIC_CRS)
    plate_centroid = na_plate_proj.geometry.unary_union.centroid

    na_quakes["distance_to_centroid_km"] = (
        na_quakes_proj.geometry.distance(plate_centroid) / 1000.0
    )

    # ================= Step 4: Find the closest one to centroid =================
    closest_quake = na_quakes.nsmallest(1, "distance_to_centroid_km").iloc[0]

    # Convert time from Unix timestamp (milliseconds) to ISO 8601 format (UTC)
    time_iso = datetime.utcfromtimestamp(closest_quake['time'] / 1000.0).strftime('%Y-%m-%dT%H:%M:%SZ')

    print("\n" + "=" * 30)
    print("The earthquake closest to the North American Plate centroid")
    print("=" * 30)
    print(f"Earthquake ID: {closest_quake['id']}")
    print(f"Location: {closest_quake['place']}")
    print(f"Time: {time_iso}")
    print(f"Magnitude: {closest_quake['mag']}")
    print(f"Latitude: {closest_quake['latitude']}")
    print(f"Longitude: {closest_quake['longitude']}")
    print(f"Distance to plate centroid: {closest_quake['distance_to_centroid_km']:.2f} km")

    # Output result to JSON file
    result = {
        "id": closest_quake['id'],
        "place": closest_quake['place'],
        "time": time_iso,
        "magnitude": closest_quake['mag'],
        "latitude": closest_quake['latitude'],
        "longitude": closest_quake['longitude'],
        "distance_to_centroid_km": round(closest_quake['distance_to_centroid_km'], 2)
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nResult saved to {output_file}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
EOF
