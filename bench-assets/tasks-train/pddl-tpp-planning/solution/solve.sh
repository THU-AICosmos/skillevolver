#!/bin/bash
# Solve TPP marketplace PDDL planning tasks.
# Self-contained: invokes pyperplan via unified_planning directly.

set -e
echo "=== marketplace TPP solver booting ==="
echo "CWD: $(pwd)"
echo "Listing /app:"
ls -la /app/ || echo "Cannot inspect /app"
echo "Listing /app/marketplace:"
ls -la /app/marketplace/ || echo "Cannot inspect /app/marketplace"

python3 << 'PYEOF'
import json
import os
import pickle
import sys

from unified_planning.io import PDDLReader
from unified_planning.shortcuts import OneshotPlanner

MANIFEST_PATH = "/app/problem.json"


def parse_pddl(dom_path, prb_path):
    rdr = PDDLReader()
    return rdr.parse_problem(dom_path, prb_path)


def synthesize_plan(parsed_prob):
    with OneshotPlanner(name="pyperplan") as engine:
        outcome = engine.solve(parsed_prob)
    return outcome.plan


def emit_plan(plan_obj, txt_destination):
    if plan_obj is None:
        raise RuntimeError(f"Planner returned no plan for {txt_destination}")

    with open(txt_destination, "w") as fh:
        for step in plan_obj.actions:
            fh.write(str(step) + "\n")

    pkl_destination = txt_destination.replace(".txt", ".pkl")
    with open(pkl_destination, "wb") as fh:
        pickle.dump(plan_obj, fh)


def handle_entry(entry):
    entry_id = entry["id"]
    dom = entry["domain"]
    prb = entry["problem"]
    out_txt = entry["plan_output"]

    print(f"  parse_pddl: {dom} + {prb}")
    parsed = parse_pddl(dom, prb)

    print(f"  synthesize_plan for {entry_id}")
    plan_obj = synthesize_plan(parsed)

    print(f"  emit_plan -> {out_txt}")
    emit_plan(plan_obj, out_txt)


print("Reading marketplace manifest ...")
with open(MANIFEST_PATH) as fh:
    mp_runner = json.load(fh)
print(f"Total entries: {len(mp_runner)}")

for slot, entry in enumerate(mp_runner):
    eid = entry["id"]
    print(f"[{slot+1}/{len(mp_runner)}] working on entry: {eid}")
    handle_entry(entry)

print("Marketplace solver finished.")
PYEOF
