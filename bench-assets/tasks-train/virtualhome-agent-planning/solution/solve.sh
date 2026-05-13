#!/bin/bash
# Logistics PDDL oracle solver (SkillsBench train variant).
# Direct functional pipeline — uses unified_planning's OneshotPlanner on each
# task and writes one plan file per entry in /app/problem.json.

set -euo pipefail

echo "[logistics-solve] starting at $(date)"
echo "[logistics-solve] pwd=$(pwd)"

python3 - <<'PYEOF'
import json
import sys
from pathlib import Path

from unified_planning.io import PDDLReader, PDDLWriter
from unified_planning.shortcuts import OneshotPlanner

MANIFEST_PATH = Path("/app/problem.json")
APP_ROOT = Path("/app")


def plan_one(domain_rel: str, problem_rel: str, output_rel: str) -> bool:
    domain_path = APP_ROOT / domain_rel
    problem_path = APP_ROOT / problem_rel
    out_path = Path(output_rel)
    if out_path.parent and str(out_path.parent) not in ("", "."):
        out_path.parent.mkdir(parents=True, exist_ok=True)

    reader = PDDLReader()
    parsed = reader.parse_problem(str(domain_path), str(problem_path))

    with OneshotPlanner(problem_kind=parsed.kind) as planner:
        outcome = planner.solve(parsed)
        print(f"  planner: {planner.name}")

    if outcome.plan is None:
        print(f"  FAIL: no plan for {problem_rel}", file=sys.stderr)
        return False

    writer = PDDLWriter(parsed)
    writer.write_plan(outcome.plan, filename=str(out_path))
    print(f"  wrote {out_path} ({len(outcome.plan.actions)} actions)")
    return True


def main() -> int:
    entries = json.loads(MANIFEST_PATH.read_text())
    print(f"[logistics-solve] {len(entries)} task(s) loaded from {MANIFEST_PATH}")

    failures = 0
    for idx, entry in enumerate(entries, start=1):
        tag = entry["id"]
        print(f"[logistics-solve] ({idx}/{len(entries)}) {tag}")
        ok = plan_one(entry["domain"], entry["problem"], entry["plan_output"])
        if not ok:
            failures += 1

    if failures:
        print(f"[logistics-solve] {failures} task(s) failed", file=sys.stderr)
        return 1
    print("[logistics-solve] all tasks planned successfully")
    return 0


sys.exit(main())
PYEOF
