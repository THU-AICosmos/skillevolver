#!/bin/bash
set -e

cat << 'EOF' > /root/estimate_coating.py
import sys
import json

sys.path.append('/root/.claude/skills/mesh-analysis/scripts')
from mesh_tool import MeshAnalyzer

# Derived from reading /root/coating_price_list.md
PRICE_PER_AREA = {
    5: 0.50,
    12: 3.25,
    37: 8.75,
    60: 12.00,
    88: 15.50,
}

def run_estimation():
    scanner = MeshAnalyzer('/root/sonar_scan.stl')
    info = scanner.analyze_largest_component()

    area = info['main_part_surface_area']
    code = info['main_part_attribute_code']

    if code not in PRICE_PER_AREA:
        print(f"Error: Coating Code {code} not found in price list")
        sys.exit(1)

    unit_cost = PRICE_PER_AREA[code]
    total = area * unit_cost

    print(f"Surface Area: {area}")
    print(f"Coating Code: {code}")
    print(f"Unit Cost: {unit_cost}")
    print(f"Total Coating Cost: {total}")

    output = {
        "total_coating_cost": total,
        "coating_code": code,
        "surface_area": area,
    }

    with open('/root/coating_estimate.json', 'w') as fout:
        json.dump(output, fout, indent=2)

if __name__ == '__main__':
    run_estimation()
EOF

python3 /root/estimate_coating.py
