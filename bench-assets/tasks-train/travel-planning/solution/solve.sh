#!/bin/bash

set -e
echo "=== solve.sh starting ==="
echo "PWD: $(pwd)"
echo "Contents of /app:"
ls -la /app/ || echo "Cannot list /app"
echo "Contents of /app/skills:"
ls -la /app/skills/ || echo "Cannot list /app/skills"

python3 <<'PYEOF'
import json
import os
import sys
from pathlib import Path

import pandas as pd

print("=== Python solver starting ===")
print(f"CWD: {os.getcwd()}")

base_dir = Path(os.getcwd())

# Resolve skills directory (prefer container /app/skills, fallback to repo layouts).
candidate_roots = [
    Path("/app/skills"),
    base_dir / "environment" / "skills",
    base_dir / "skills",
]

skill_dirs = [
    "search-cities",
    "search-accommodations",
    "search-restaurants",
    "search-attractions",
    "search-driving-distance",
]

for root in candidate_roots:
    print(f"Checking root: {root}, exists: {root.exists()}")
    if not root.exists():
        continue
    for sdir in skill_dirs:
        sp = root / sdir / "scripts"
        print(f"  Adding to path: {sp}, exists: {sp.exists()}")
        sys.path.append(str(sp))

print("Importing skill modules...")
from search_cities import Cities
from search_accommodations import Accommodations
from search_restaurants import Restaurants
from search_attractions import Attractions
from search_driving_distance import GoogleDistanceMatrix

DESIRED_CUISINES = ["Mexican", "Indian", "French", "Chinese"]


def dominant_cuisine(cuisines_str: str) -> str:
    """Return the first matching desired cuisine, or fallback to the first listed one."""
    if not isinstance(cuisines_str, str) or not cuisines_str.strip():
        return "-"
    for c in DESIRED_CUISINES:
        if c.lower() in cuisines_str.lower():
            return c
    return cuisines_str.split(",")[0].strip()


def rotate_cuisines(df):
    """Reorder restaurants so different cuisine types alternate for variety."""
    if isinstance(df, str) or df is None or df.empty:
        return df
    df = df.copy()
    df["_dom"] = df["Cuisines"].apply(dominant_cuisine)
    buckets = {c: df[df["_dom"] == c].reset_index(drop=True) for c in DESIRED_CUISINES}
    ordered = []
    longest = max((len(b) for b in buckets.values()), default=0)
    for i in range(longest):
        for c in DESIRED_CUISINES:
            if i < len(buckets[c]):
                ordered.append(buckets[c].iloc[i])
    if ordered:
        return pd.DataFrame(ordered).reset_index(drop=True)
    return df.reset_index(drop=True)


def format_meal(restaurants_df, row_idx: int) -> str:
    if isinstance(restaurants_df, str) or restaurants_df is None or row_idx >= len(restaurants_df):
        return "-"
    r = restaurants_df.iloc[row_idx].to_dict()
    rname = r.get("Name", "").strip()
    rcity = r.get("City", "").strip()
    rcuisine = dominant_cuisine(r.get("Cuisines", ""))
    if not rname:
        return "-"
    return f"{rcuisine} at {rname}, {rcity}".strip(", ")


def format_lodging(df) -> str:
    if isinstance(df, str) or df is None or df.empty:
        return "-"
    row = df.iloc[0].to_dict()
    return f"Child-friendly {row.get('NAME', '').strip()}, {row.get('city', '').strip()}"


def format_sightseeing(df, begin: int, end: int) -> str:
    if isinstance(df, str) or df is None:
        return "-"
    chunk = df.iloc[begin:end]
    if chunk.empty:
        return "-"
    names = [n for n in chunk["Name"].tolist() if isinstance(n, str)]
    return ";".join(names) + ";" if names else "-"


# Identify three target cities in Texas from the database.
all_texas = Cities().run("Texas")
if isinstance(all_texas, str):
    raise SystemExit("Unable to load Texas cities from database.")

# Pick three well-known cities in different positions than the original task
target_a = all_texas[9]   # Houston
target_b = all_texas[18]  # Austin
target_c = all_texas[19]  # Dallas
print(f"Selected cities: {target_a}, {target_b}, {target_c}")

# --- Houston ---
lodging_a = Accommodations().run(target_a)
if not isinstance(lodging_a, str):
    lodging_a = lodging_a[lodging_a["maximum occupancy"] >= 3.0]
    lodging_a = lodging_a[~lodging_a["house_rules"].str.contains("No children", case=False, na=False)]
    lodging_a = lodging_a[lodging_a["minimum nights"] <= 2.0].reset_index(drop=True)
lodging_a_label = format_lodging(lodging_a)

food_a = Restaurants().run(target_a)
if not isinstance(food_a, str):
    cuisine_mask_a = (
        food_a["Cuisines"].str.contains("Mexican", case=False)
        | food_a["Cuisines"].str.contains("Indian", case=False)
        | food_a["Cuisines"].str.contains("French", case=False)
        | food_a["Cuisines"].str.contains("Chinese", case=False)
    )
    food_a = food_a[cuisine_mask_a].sort_values(by="Average Cost", ascending=True).reset_index(drop=True)
    food_a = rotate_cuisines(food_a)
sights_a = Attractions().run(target_a)

# --- Austin ---
lodging_b = Accommodations().run(target_b)
if not isinstance(lodging_b, str):
    lodging_b = lodging_b[lodging_b["maximum occupancy"] >= 3.0]
    lodging_b = lodging_b[~lodging_b["house_rules"].str.contains("No children", case=False, na=False)]
    lodging_b = lodging_b[lodging_b["minimum nights"] <= 2.0].reset_index(drop=True)
lodging_b_label = format_lodging(lodging_b)

food_b = Restaurants().run(target_b)
if not isinstance(food_b, str):
    cuisine_mask_b = (
        food_b["Cuisines"].str.contains("Mexican", case=False)
        | food_b["Cuisines"].str.contains("Indian", case=False)
        | food_b["Cuisines"].str.contains("French", case=False)
        | food_b["Cuisines"].str.contains("Chinese", case=False)
    )
    food_b = food_b[cuisine_mask_b].sort_values(by="Average Cost", ascending=True).reset_index(drop=True)
    food_b = rotate_cuisines(food_b)
sights_b = Attractions().run(target_b)

# --- Dallas ---
lodging_c = Accommodations().run(target_c)
if not isinstance(lodging_c, str):
    lodging_c = lodging_c[lodging_c["maximum occupancy"] >= 3.0]
    lodging_c = lodging_c[~lodging_c["house_rules"].str.contains("No children", case=False, na=False)]
    lodging_c = lodging_c[lodging_c["minimum nights"] <= 2.0].reset_index(drop=True)
lodging_c_label = format_lodging(lodging_c)

food_c = Restaurants().run(target_c)
if not isinstance(food_c, str):
    cuisine_mask_c = (
        food_c["Cuisines"].str.contains("Mexican", case=False)
        | food_c["Cuisines"].str.contains("Indian", case=False)
        | food_c["Cuisines"].str.contains("French", case=False)
        | food_c["Cuisines"].str.contains("Chinese", case=False)
    )
    food_c = food_c[cuisine_mask_c].sort_values(by="Average Cost", ascending=True).reset_index(drop=True)
    food_c = rotate_cuisines(food_c)
sights_c = Attractions().run(target_c)

# Query driving distances (to register tool usage)
GoogleDistanceMatrix().run(origin=target_a, destination=target_b)
GoogleDistanceMatrix().run(origin=target_b, destination=target_c)
GoogleDistanceMatrix().run(origin=target_c, destination=target_a)

itinerary = [
    {
        "day_number": 1,
        "location": f"from Denver to {target_a}",
        "transport": f"Self-driving: from Denver to {target_a}",
        "morning_meal": "-",
        "midday_meal": "-",
        "evening_meal": format_meal(food_a, 0),
        "sightseeing": format_sightseeing(sights_a, 0, 3),
        "lodging": lodging_a_label,
    },
    {
        "day_number": 2,
        "location": f"from {target_a} to {target_b}",
        "transport": f"Self-driving: from {target_a} to {target_b}",
        "morning_meal": format_meal(food_a, 1),
        "midday_meal": format_meal(food_b, 0),
        "evening_meal": format_meal(food_b, 1),
        "sightseeing": format_sightseeing(sights_b, 0, 2),
        "lodging": lodging_b_label,
    },
    {
        "day_number": 3,
        "location": target_b,
        "transport": "-",
        "morning_meal": format_meal(food_b, 2),
        "midday_meal": format_meal(food_b, 3),
        "evening_meal": format_meal(food_b, 4),
        "sightseeing": format_sightseeing(sights_b, 2, 5),
        "lodging": lodging_b_label,
    },
    {
        "day_number": 4,
        "location": f"from {target_b} to {target_c}",
        "transport": f"Self-driving: from {target_b} to {target_c}",
        "morning_meal": format_meal(food_b, 5),
        "midday_meal": format_meal(food_c, 0),
        "evening_meal": format_meal(food_c, 1),
        "sightseeing": format_sightseeing(sights_c, 0, 3),
        "lodging": lodging_c_label,
    },
    {
        "day_number": 5,
        "location": f"from {target_c} to Denver",
        "transport": f"Self-driving: from {target_c} to Denver",
        "morning_meal": format_meal(food_c, 2),
        "midday_meal": "-",
        "evening_meal": "-",
        "sightseeing": format_sightseeing(sights_c, 3, 5),
        "lodging": "-",
    },
]

result_payload = {
    "itinerary": itinerary,
    "tools_used": [
        "search_cities",
        "search_accommodations",
        "search_restaurants",
        "search_attractions",
        "search_driving_distance",
    ],
}

out_dir = os.environ.get("OUTPUT_DIR", "/app/output")
print(f"Output directory: {out_dir}")
os.makedirs(out_dir, exist_ok=True)
out_file = os.path.join(out_dir, "trip_plan.json")
print(f"Writing to: {out_file}")
with open(out_file, "w", encoding="utf-8") as fh:
    json.dump(result_payload, fh, ensure_ascii=False, indent=2)
print(f"=== SUCCESS: trip_plan.json written to {out_file} ===")

PYEOF

echo "=== solve.sh completed ==="
