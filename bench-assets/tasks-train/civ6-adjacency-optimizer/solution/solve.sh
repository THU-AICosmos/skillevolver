#!/bin/bash
# Oracle solution - outputs the optimal placement from ground truth for scenario_5
#
# This is a reference solution showcasing the optimal adjacency bonus.
# Submitters should replace this with their own optimization algorithm.

python3 << 'PYEOF'
import json
from pathlib import Path

RESULT_DIR = Path("/output")
ANSWERS_DIR = Path("/solution/ground_truths")

RESULT_DIR.mkdir(parents=True, exist_ok=True)

sid = "scenario_5"
answer_file = ANSWERS_DIR / sid / "ground_truth.json"
result_file = RESULT_DIR / f"{sid}.json"

with open(answer_file) as fh:
    answer_data = json.load(fh)

ref = answer_data.get("reference_solution", {})

output = {
    "city_center": ref.get("city_center"),
    "placements": ref.get("placements", {}),
    "adjacency_bonuses": ref.get("adjacency_bonuses", {}),
    "total_adjacency": answer_data.get("optimal_adjacency", 0)
}

with open(result_file, "w") as fh:
    json.dump(output, fh, indent=2)

print(f"{sid}: Written to {result_file} (total_adjacency: {output['total_adjacency']})")
print("\nOracle solution complete.")
PYEOF
