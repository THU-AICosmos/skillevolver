#!/usr/bin/env python3
"""Aggregate SkillEvolver run results.

Walks `evolved-skills/<version>/<task>/<timestamp>/` and writes, per pipeline
version, two artefacts next to the runs:

  evolved-skills/<version>/results-db.jsonl   — one JSON record per run
  evolved-skills/<version>/report.md          — per-task pass-rate table

For each run we also do the **Oracle Peek Audit** (optional): grep `agent.log`
for reads of `train-context/solution/` or `train-context/tests/test_outputs.py`.
This is the same defense the original paper uses to spot runs that leaned on
the training oracle — useful for sanity-checking your own sweeps.

Usage:
    python scripts/aggregate_results.py                # all versions
    python scripts/aggregate_results.py --version evolver
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVOLVED_SKILLS_DIR = PROJECT_ROOT / "evolved-skills"

ORACLE_READ_PATTERNS = [
    re.compile(r"train-context/solution/"),
    re.compile(r"train-context/tests/test_outputs\.py"),
]


def _relpath(p: Path) -> str:
    try:
        return str(p.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(p)


def _audit_oracle_reads(agent_log: Path) -> dict[str, int]:
    counts = {"solution": 0, "test_outputs": 0}
    if not agent_log.exists():
        return counts
    try:
        text = agent_log.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return counts
    counts["solution"] = len(ORACLE_READ_PATTERNS[0].findall(text))
    counts["test_outputs"] = len(ORACLE_READ_PATTERNS[1].findall(text))
    return counts


def _summarise_run(run_dir: Path) -> dict[str, Any] | None:
    result_path = run_dir / "result.json"
    if not result_path.exists():
        return None
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  warn: cannot read {result_path}: {exc}", file=sys.stderr)
        return None

    validation = result.get("phases", {}).get("validation") or {}
    record = {
        "task": result.get("task") or run_dir.parent.name,
        "version": result.get("pipeline_version") or run_dir.parent.parent.name,
        "timestamp": result.get("timestamp") or run_dir.name,
        "run_dir": _relpath(run_dir),
        "model": result.get("model"),
        "n_passed": validation.get("n_passed"),
        "n_attempts": validation.get("n_attempts"),
        "pass_rate": validation.get("pass_rate"),
        "agent_cost_usd": result.get("agent_cost_usd"),
        "harbor_cost_usd": result.get("harbor_cost_usd"),
        "oracle_reads": _audit_oracle_reads(run_dir / "agent.log"),
    }
    return record


def _latest_runs(version_dir: Path) -> list[Path]:
    """For each task under <version>/, pick the most recent timestamp dir."""
    runs: list[Path] = []
    for task_dir in sorted(p for p in version_dir.iterdir() if p.is_dir()):
        timestamp_dirs = sorted(
            (p for p in task_dir.iterdir() if p.is_dir() and (p / "result.json").exists()),
            reverse=True,
        )
        if timestamp_dirs:
            runs.append(timestamp_dirs[0])
    return runs


def aggregate_version(version_dir: Path) -> list[dict[str, Any]]:
    records = []
    for run_dir in _latest_runs(version_dir):
        rec = _summarise_run(run_dir)
        if rec is not None:
            records.append(rec)
    return records


def write_jsonl(records: list[dict[str, Any]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")


def write_report(records: list[dict[str, Any]], out: Path, version: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {version} — run summary",
        "",
        f"Tasks aggregated: **{len(records)}** (latest run per task)",
        "",
        "| Task | Pass | Pass rate | Cost (agent + harbor) | Oracle reads (sol / tests) |",
        "|------|------|-----------|-----------------------|----------------------------|",
    ]
    total_pass_rate = 0.0
    n_with_rate = 0
    for rec in sorted(records, key=lambda r: r["task"]):
        pr = rec.get("pass_rate")
        pr_str = f"{pr:.2f}" if isinstance(pr, (int, float)) else "—"
        if isinstance(pr, (int, float)):
            total_pass_rate += pr
            n_with_rate += 1
        passed = rec.get("n_passed")
        attempts = rec.get("n_attempts")
        pass_str = f"{passed}/{attempts}" if attempts is not None else "—"
        cost_agent = rec.get("agent_cost_usd") or 0.0
        cost_harbor = rec.get("harbor_cost_usd") or 0.0
        cost_str = f"${cost_agent + cost_harbor:.2f}"
        o = rec.get("oracle_reads") or {}
        oracle_str = f"{o.get('solution', 0)} / {o.get('test_outputs', 0)}"
        lines.append(f"| {rec['task']} | {pass_str} | {pr_str} | {cost_str} | {oracle_str} |")
    if n_with_rate:
        avg = total_pass_rate / n_with_rate
        lines.insert(3, f"Mean validation pass rate: **{avg:.3f}**")
        lines.insert(4, "")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        help="Pipeline version subdirectory (default: aggregate every version found)",
    )
    parser.add_argument(
        "--evolved-skills-dir",
        type=Path,
        default=EVOLVED_SKILLS_DIR,
        help=f"Root of evolved-skills/ (default: {EVOLVED_SKILLS_DIR})",
    )
    args = parser.parse_args()

    if not args.evolved_skills_dir.exists():
        print(f"error: {args.evolved_skills_dir} does not exist", file=sys.stderr)
        return 1

    if args.version:
        version_dirs = [args.evolved_skills_dir / args.version]
    else:
        version_dirs = [p for p in args.evolved_skills_dir.iterdir() if p.is_dir()]

    for version_dir in sorted(version_dirs):
        if not version_dir.is_dir():
            print(f"skip: {version_dir} is not a directory", file=sys.stderr)
            continue
        records = aggregate_version(version_dir)
        if not records:
            print(f"  {version_dir.name}: no runs with result.json found")
            continue
        write_jsonl(records, version_dir / "results-db.jsonl")
        write_report(records, version_dir / "report.md", version_dir.name)
        print(f"  {version_dir.name}: aggregated {len(records)} run(s) → {version_dir}/report.md")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
