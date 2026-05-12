"""
Benchmark Runner

Runs all 4 conditions for a SkillsBench task and compares results.

Conditions:
  1. Oracle (validate task works)
  2. No Skills (baseline)
  3. Human-Curated Skills (from tasks/)
  4. Evolved Skills (from skill-creator agent)

Usage:
    python -m skill-creator.agent.benchmark --task court-form-filling
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .config import (
    EVOLVED_SKILLS_DIR,
    PROJECT_ROOT,
    SKILLSBENCH_ROOT,
    TASKS_DIR,
    TASKS_NO_SKILLS_DIR,
)


def run_harbor(task_path: str, agent: str, model: str | None = None, label: str = "") -> dict:
    """Run a single harbor benchmark."""
    cmd = ["uv", "run", "harbor", "run", "-p", task_path, "-a", agent]
    if model:
        cmd.extend(["-m", model])

    print(f"\n{'='*60}")
    print(f"Running: {label or ' '.join(cmd)}")
    print(f"{'='*60}")

    result = subprocess.run(
        cmd,
        cwd=str(SKILLSBENCH_ROOT),
        capture_output=True,
        text=True,
        timeout=1800,  # 30 min timeout
    )

    output = {
        "label": label,
        "command": " ".join(cmd),
        "returncode": result.returncode,
        "stdout": result.stdout[-2000:] if result.stdout else "",
        "stderr": result.stderr[-2000:] if result.stderr else "",
    }

    if result.returncode == 0:
        print(f"  PASSED")
    else:
        print(f"  FAILED (exit code {result.returncode})")
        if result.stderr:
            print(f"  stderr: {result.stderr[-500:]}")

    return output


def run_benchmark(task_name: str, model: str = "anthropic/claude-sonnet-4-5"):
    """Run all 4 conditions for a task."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = PROJECT_ROOT / "benchmark-results" / task_name / timestamp
    results_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # Condition 0: Oracle (validate)
    oracle_result = run_harbor(
        task_path=f"tasks/{task_name}",
        agent="oracle",
        label="Oracle (validation)",
    )
    results["oracle"] = oracle_result

    # Condition 1: No Skills
    no_skills_path = f"tasks-no-skills/{task_name}"
    if not (SKILLSBENCH_ROOT / no_skills_path).exists():
        print(f"Warning: {no_skills_path} not found, using tasks/ without skills copy")
        no_skills_path = f"tasks/{task_name}"

    no_skills_result = run_harbor(
        task_path=no_skills_path,
        agent="claude-code",
        model=model,
        label="No Skills (baseline)",
    )
    results["no_skills"] = no_skills_result

    # Condition 2: Human-Curated Skills
    curated_result = run_harbor(
        task_path=f"tasks/{task_name}",
        agent="claude-code",
        model=model,
        label="Human-Curated Skills",
    )
    results["curated_skills"] = curated_result

    # Condition 3: Evolved Skills
    evolved_task_dir = PROJECT_ROOT / "tasks-evolved-skills" / task_name
    if evolved_task_dir.exists():
        evolved_result = run_harbor(
            task_path=str(evolved_task_dir),
            agent="claude-code",
            model=model,
            label="Evolved Skills (skill-creator)",
        )
        results["evolved_skills"] = evolved_result
    else:
        print(f"\nSkipping evolved skills — not found at {evolved_task_dir}")
        print("Run the skill generator first: python -m skill-creator.agent.run --task {task_name}")
        results["evolved_skills"] = {"label": "Evolved Skills", "status": "skipped"}

    # Save results
    results_file = results_dir / "results.json"
    results_file.write_text(json.dumps(results, indent=2))
    print(f"\n{'='*60}")
    print(f"Results saved to: {results_file}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"BENCHMARK SUMMARY: {task_name}")
    print(f"{'='*60}")
    print(f"{'Condition':<30} {'Status':<10}")
    print(f"{'-'*40}")
    for key, val in results.items():
        status = "PASS" if val.get("returncode") == 0 else "FAIL" if "returncode" in val else "SKIP"
        print(f"{val.get('label', key):<30} {status:<10}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Run SkillsBench benchmark with all conditions")
    parser.add_argument("--task", required=True, help="Task name")
    parser.add_argument("--model", default="anthropic/claude-sonnet-4-5", help="Model for agent runs")
    args = parser.parse_args()

    run_benchmark(args.task, args.model)


if __name__ == "__main__":
    main()
