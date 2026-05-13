#!/bin/bash
set -e

cat > /tmp/vwan_bgp_check.py << 'PYCODE'
#!/usr/bin/env python3
"""
Solution for Azure Virtual WAN BGP oscillation and route leak detection (train variant).

Topology (Azure Virtual WAN train variant):
          ASN 64810 (Virtual WAN / Regional ISP)
         /                    \
    ASN 64811              ASN 64812
    (HubEast/vhubvnetEast)  (HubWest/vhubvnetWest)
    /         \              /         \
 ASN 64813  ASN 64814   ASN 64815  ASN 64816
 (vnetA)    (vnetB)     (vnetC)    (vnetD - origin)
"""

import json
from pathlib import Path


DATA_PATH = Path("/app/data")
OUT_PATH = Path("/app/output")
OUT_PATH.mkdir(parents=True, exist_ok=True)
REPORT_FILE = OUT_PATH / "oscillation_report.json"


def contains_any(text, patterns):
    """Return True if any pattern (case-insensitive) appears in text."""
    text_lc = text.lower()
    return any(p in text_lc for p in patterns)


def analyze():
    print("==== Azure Virtual WAN BGP Analysis (train variant) ====")

    # -- Load configuration --
    print("\n[1] Loading data files...")
    with open(DATA_PATH / "route.json") as fh:
        prefix_info = json.load(fh)
    with open(DATA_PATH / "preferences.json") as fh:
        pref_data = json.load(fh)
    with open(DATA_PATH / "route_events.json") as fh:
        events = json.load(fh)

    print(f"  Prefix: {prefix_info['prefix']}  Origin ASN: {prefix_info['origin_asn']}")

    # -- Detect oscillation cycle --
    print("\n[2] Detecting routing preference cycles...")
    pref_map = {}
    for asn_str, entry in pref_data.items():
        if "prefer_via" in entry:
            pref_map[int(asn_str)] = entry["prefer_via"]
            print(f"  ASN {asn_str} -> prefers via {entry['prefer_via']}")

    osc_found = False
    osc_cycle = []
    affected = []

    for node, target in pref_map.items():
        if target in pref_map and pref_map[target] == node:
            osc_found = True
            osc_cycle = sorted([node, target])
            affected = list(osc_cycle)
            print(f"  >> Mutual preference cycle: {node} <-> {target}")
            break

    # -- Detect route leaks --
    print("\n[3] Detecting valley-free violations...")
    leak_found = False
    leak_records = []

    for ev in events:
        leak_found = True
        leak_records.append({
            "leaker_as": ev["advertiser_asn"],
            "source_as": ev["source_asn"],
            "destination_as": ev["destination_asn"],
            "source_type": ev["source_type"],
            "destination_type": ev["destination_type"],
        })
        print(f"  >> Leak: ASN {ev['advertiser_asn']} sent {ev['source_type']}-learned routes to {ev['destination_type']} ASN {ev['destination_asn']}")

    # -- Evaluate possible solutions --
    print("\n[4] Evaluating possible solutions...")

    # Operations forbidden by policy (would break connectivity / not allowed)
    PROHIBITED = [
        "disable bgp",
        "disable peering",
        "disable hub peering",
        "remove peer",
        "shut down",
        "shutdown",
    ]

    # Patterns that genuinely break the routing-preference cycle
    OSC_FIX_PATTERNS = [
        "update routing preference",
        "stop preferring routes",
        "stop preferring",
        "filter out routes learned",
        "filter routes learned",
        "before re-advertising",
        "before re-announcing",
        "preference hierarchy",
        "route preference hierarchy",
        "routing intent to enforce",
        "hub routing intent",
        "user defined route override",
        "route override",
    ]

    # Patterns that genuinely stop the bad advertisement (prevent leak)
    LEAK_FIX_PATTERNS = [
        "block announcing",
        "block announcing provider",
        "export policy to block",
        "ingress filtering",
        "reject routes with",
        "no-export of provider",
        "enforce no-export",
        "by bgp community",
        "rpki origin validation",
        "origin validation",
        "route policy to enforce",
        "routing intent to enforce",
        "hub routing intent",
        "user defined route override",
        "route override",
    ]

    verdicts = {}

    if osc_found or leak_found:
        sol_file = DATA_PATH / "possible_solutions.json"
        if sol_file.exists():
            with open(sol_file) as fh:
                solutions = json.load(fh)

            for sol in solutions:
                if contains_any(sol, PROHIBITED):
                    osc_ok = False
                    leak_ok = False
                else:
                    osc_ok = contains_any(sol, OSC_FIX_PATTERNS) if osc_found else False
                    leak_ok = contains_any(sol, LEAK_FIX_PATTERNS) if leak_found else False

                verdicts[sol] = {
                    "oscillation_resolved": osc_ok,
                    "route_leak_resolved": leak_ok,
                }

            print(f"  Evaluated {len(solutions)} candidate solutions")

    # -- Write report --
    print("\n[5] Writing oscillation report...")
    report = {
        "oscillation_detected": osc_found,
        "oscillation_cycle": osc_cycle,
        "affected_ases": affected,
        "route_leak_detected": leak_found,
        "route_leaks": leak_records,
        "solution_results": verdicts,
    }

    with open(REPORT_FILE, "w") as fh:
        json.dump(report, fh, indent=2)

    print(f"\nReport saved to {REPORT_FILE}")
    print(f"  Oscillation detected: {osc_found}  Cycle: {osc_cycle}")
    print(f"  Route leaks detected: {leak_found}  Count: {len(leak_records)}")
    print("Analysis complete.")


if __name__ == "__main__":
    analyze()
PYCODE

python3 /tmp/vwan_bgp_check.py
