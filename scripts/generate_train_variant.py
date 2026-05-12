#!/usr/bin/env python3
"""Generate a training variant of a SkillsBench task using Claude Agent SDK.

Claude gets tools (Bash, Write, Read, etc.) and iterates: generate → verify → fix → verify.

Usage:
    python scripts/generate_train_variant.py --task court-form-filling
    python scripts/generate_train_variant.py --task court-form-filling --dry-run-only
    python scripts/generate_train_variant.py --all
    python scripts/generate_train_variant.py --all --skip-verify
"""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import anyio
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

PROJECT_ROOT = Path(__file__).parent.parent
SKILLSBENCH_ROOT = PROJECT_ROOT / "Benchmarks" / "skillsbench"
TASKS_DIR = SKILLSBENCH_ROOT / "tasks"
TASKS_TRAIN_DIR = SKILLSBENCH_ROOT / "tasks-train"

# Tasks that need sub-task split (opaque binary files)
SUBTASK_SPLIT_TASKS = {
    "earthquake-phase-association",
    "gravitational-wave-detection",
    "video-silence-remover",
    "mario-coin-counting",
    "multilingual-video-dubbing",
    "pedestrian-traffic-counting",
    "jpg-ocr-stat",
    "seismic-phase-picking",
    "dapt-intrusion-detection",
    "paper-anonymizer",
    "manufacturing-equipment-maintenance",
    # Video/media tasks with opaque binary data
    "speaker-diarization-subtitles",
    "video-filler-word-remover",
    "video-tutorial-indexer",
    "dynamic-object-aware-egomotion",
}

# No tasks skipped — full 87-task dataset needed for paper completeness
SKIP_TASKS: set[str] = set()


def get_strategy(task_name: str) -> str:
    """Determine generation strategy for a task."""
    if task_name in SUBTASK_SPLIT_TASKS:
        return "subtask_split"
    return "generate_new"


def build_agent_prompt(task_name: str, strategy: str, output_dir: Path) -> str:
    """Build the prompt for the Claude agent that generates the training variant."""
    original_dir = TASKS_DIR / task_name
    traingen_python = Path.home() / "miniconda3" / "envs" / "traingen" / "bin" / "python"

    strategy_instruction = ""
    if strategy == "subtask_split":
        strategy_instruction = f"""
## Strategy: Sub-Task Split (SHARED-DATA — flagged for separate reporting)

This task has binary data files that can't be regenerated. You must:
1. Copy the original data files from {original_dir}/environment/ to {output_dir}/environment/
   (skip Dockerfile and skills/)
2. Create a REDUCED version of test_outputs.py that tests only 30-50% of the original checks
   - Choose a DIFFERENT subset of metrics/features than the original tests
   - Use DIFFERENT output file paths and variable names
3. Create a matching reduced solve.sh with DIFFERENT code organization (not just line deletion)
4. Rewrite instruction.md to describe the reduced scope in your own words (don't copy-paste)
5. Copy the Dockerfile unchanged

NOTE: This variant shares input data with the original test task. Results will be reported
separately in the paper to address potential memorization concerns.
"""
    else:
        strategy_instruction = f"""
## Strategy: Generate New Data

Create DIFFERENT data that tests the same skills/knowledge but with different concrete values.
- For text/CSV/JSON data: create new files with different values
- For binary files (xlsx, pdf, npy, npz): write a Python generation script and run it
  Use {traingen_python} to run generation scripts (has numpy, openpyxl, python-docx, python-pptx, pypdf, reportlab, pandas)
  Do NOT use domain-specific libraries (jax, torch, etc.) — numpy only for array generation

### Anti-Leakage Rules (CRITICAL)
- Do NOT reuse any data files from the original task (no symlinks, no copies)
- Do NOT use the same form/template/document as the original (e.g., if original fills an SC-100 form, use a completely different form type)
- Your solve.sh should use DIFFERENT variable names, different output paths, and ideally a different code organization (helper functions, class vs script, etc.) — even if it uses the same libraries
- An evaluator comparing your variant side-by-side with the original should see ZERO copy-paste overlap
"""

    return f"""You are generating a TRAINING VARIANT of a SkillsBench task.

## Purpose

This training variant is used to prevent memorization. An AI agent will explore (practice) on YOUR variant,
then be tested on the ORIGINAL task. If your variant is too similar to the original, the agent can memorize
the exact solution steps instead of learning the underlying skills. Your variant must be OBVIOUSLY DIFFERENT
so the agent must learn transferable knowledge.

## Original Task: {task_name}

The original task files are at: {original_dir}/
Read them ALL to deeply understand what the task does:
- {original_dir}/instruction.md — task description
- {original_dir}/tests/test_outputs.py — test assertions
- {original_dir}/solution/solve.sh — oracle solution
- {original_dir}/environment/Dockerfile — Docker environment
- {original_dir}/environment/ — data files (if any)

{strategy_instruction}

## Diversity Requirements (CRITICAL)

Your variant must differ from the original in OBVIOUS, STRUCTURAL ways — not just swapping values:

1. **Different scenario/story** — If the original is about filling a court form for a landlord dispute,
   yours should be about a different type of claim (auto accident, unpaid wages, property damage).
   Don't just change names; change the entire scenario.

2. **Different data structure** — If the original has 5 sub-tasks, yours should have different sub-tasks
   that test the same underlying skills. E.g., if original tests "compute mean of rows" and "square elements",
   yours could test "compute std of columns" and "apply exp function". Same JAX skills needed, different operations.

3. **Different quantities** — Different number of items, different dimensions, different counts.
   If original has 10 invoices, yours should have 7 or 15. Different proportions of pass/fail cases.

4. **Different expected outputs** — test_outputs.py must check for different specific values.
   If original checks for "John Smith" in the output, yours checks for completely different names/values.

5. **Same underlying knowledge needed** — Despite all the surface differences, solving your variant
   requires the SAME domain knowledge, libraries, and techniques as the original.

Think of it like a math exam: the original asks "solve 2x + 3 = 7", your variant asks "solve 5y - 4 = 11".
Same skill (linear equations), completely different problem. NOT "solve 2x + 3 = 9" (just changing a number).

## Output Directory

Write ALL generated files to: {output_dir}/
Required structure:
- {output_dir}/instruction.md
- {output_dir}/environment/Dockerfile
- {output_dir}/tests/test.sh          ← Harbor verifier entry point (see below)
- {output_dir}/tests/test_outputs.py
- {output_dir}/solution/solve.sh

Also copy {original_dir}/task.toml to {output_dir}/task.toml unchanged.

### tests/test.sh (REQUIRED)
This is the Harbor verifier entry point. Copy it from the original task ({original_dir}/tests/test.sh) and adapt if needed:
- If your variant uses the same Python packages as the original, copy test.sh unchanged.
- If your variant's test_outputs.py imports different packages, update the `--with` flags in the `uvx` command accordingly.
- The script MUST write `1` or `0` to `/logs/verifier/reward.txt` based on pytest exit code.

## Verification

After generating all files, verify your work:
1. Build Docker image: `docker build -t train-verify-{task_name} {output_dir}/environment/`
2. Run solve.sh + test_outputs.py in one container:
   ```
   docker run --rm \
     -v {output_dir}/solution/solve.sh:/tmp/solve.sh:ro \
     -v {output_dir}/tests/test_outputs.py:/tmp/test_outputs.py:ro \
     train-verify-{task_name} \
     bash -c "bash /tmp/solve.sh && python -m pytest /tmp/test_outputs.py -v"
   ```
3. If tests fail, debug and fix. Iterate until solve.sh + test_outputs.py pass.
4. Clean up: `docker rmi train-verify-{task_name}`

## Important Rules
- The variant must test the SAME underlying skills/knowledge as the original
- The variant must be OBVIOUSLY DIFFERENT in scenario, data structure, and quantities
- An agent looking at both variants should NOT be able to copy-paste solution steps between them
- solve.sh must pass test_outputs.py — verify this before finishing
- When done, output exactly: "GENERATION COMPLETE" as your final message
"""


async def run_generation_agent(
    task_name: str,
    strategy: str,
    output_dir: Path,
    model: str = "claude-opus-4-6",
    max_turns: int = 50,
    max_budget: float = 5.0,
) -> bool:
    """Launch Agent SDK session to generate and verify a training variant."""
    prompt = build_agent_prompt(task_name, strategy, output_dir)

    # Ensure output dirs exist
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Launching agent (model={model}, budget=${max_budget})...")

    generation_complete = False
    result_text = ""

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            cwd=str(output_dir),
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            model=model,
            max_turns=max_turns,
            max_budget_usd=max_budget,
            permission_mode="bypassPermissions",
        ),
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text.strip()
                    if text:
                        # Show abbreviated progress
                        if len(text) > 200:
                            print(f"  Agent: {text[:200]}...")
                        else:
                            print(f"  Agent: {text}")
                    if "GENERATION COMPLETE" in (block.text or ""):
                        generation_complete = True
                elif isinstance(block, ToolUseBlock):
                    name = block.name
                    inp = block.input or {}
                    if name == "Bash":
                        print(f"  > [Bash] {inp.get('description', inp.get('command', '')[:80])}")
                    elif name in ("Write", "Edit"):
                        print(f"  > [{name}] {inp.get('file_path', '')}")
                    elif name == "Read":
                        print(f"  > [Read] {inp.get('file_path', '')}")
        elif isinstance(message, ResultMessage):
            result_text = message.result or ""
            cost = f"${message.total_cost_usd:.2f}" if message.total_cost_usd else "N/A"
            print(f"  Agent done. Turns: {message.num_turns}, Cost: {cost}")

    return generation_complete


def _parse_task_env(task_dir: Path) -> list[str]:
    """Parse task.toml verifier.env and solution.env → list of -e KEY=VAL docker args."""
    toml_path = task_dir / "task.toml"
    if not toml_path.exists():
        return []
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore
    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return []
    env_args: list[str] = []
    seen: set[str] = set()
    for section in ("verifier", "solution"):
        env = data.get(section, {}).get("env", {})
        if isinstance(env, dict):
            for k, v in env.items():
                if k in seen:
                    continue
                seen.add(k)
                env_args.extend(["-e", f"{k}={v}"])
    return env_args


def verify_variant(task_name: str) -> bool:
    """Dry-run verification: build Docker, run solve.sh, check test_outputs.py."""
    task_dir = TASKS_TRAIN_DIR / task_name
    print(f"  Verifying training variant for {task_name}...")

    env_dir = task_dir / "environment"
    if not env_dir.exists():
        print(f"  ERROR: No environment/ directory in {task_dir}")
        return False

    task_env_args = _parse_task_env(task_dir)

    image_tag = f"skillsbench-train-{task_name}"
    build_cmd = ["docker", "build", "-t", image_tag, str(env_dir)]
    try:
        result = subprocess.run(build_cmd, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        print(f"  Docker build FAILED: timed out after 1800s")
        return False
    if result.returncode != 0:
        print(f"  Docker build FAILED:\n{result.stderr[-500:]}")
        return False
    print("  Docker build OK")

    solve_dir = task_dir / "solution"
    solve_path = solve_dir / "solve.sh"
    test_path = task_dir / "tests" / "test_outputs.py"

    if not solve_path.exists():
        print("  WARNING: No solve.sh found, skipping solve verification")
        return True
    if not test_path.exists():
        print("  WARNING: No test_outputs.py found, skipping test verification")
        return True

    # Mount entire solution/ and tests/ directories (may contain solve.py, expected_output.json, etc.)
    tests_dir = task_dir / "tests"
    test_sh_path = tests_dir / "test.sh"
    if test_sh_path.exists():
        # Use the real Harbor verifier entry point
        # Mount host tests at /host_tests (ro) and overlay into /tests at runtime,
        # preserving container files like run_passed.sh symlinks that some tasks need.
        # Accept any reward >= 1.0 (handles "1", "1.0", "1.00" etc.)
        verify_script = (
            "mkdir -p /tests && "
            "cp -rL /host_tests/. /tests/ 2>/dev/null || true && "
            "bash /solution/solve.sh && "
            "mkdir -p /logs/verifier && "
            "bash /tests/test.sh && "
            "awk 'NR==1{if ($1+0 >= 1.0) exit 0; else exit 1}' /logs/verifier/reward.txt"
        )
        run_cmd = [
            "docker", "run", "--rm",
            "--network", "host",
            *task_env_args,
            "-v", f"{solve_dir}:/solution:ro",
            "-v", f"{tests_dir}:/host_tests:ro",
            image_tag,
            "bash", "-c", verify_script,
        ]
    else:
        # Fallback: pip install pytest then run directly (use python3, not python)
        verify_script = (
            "bash /solution/solve.sh && "
            "pip install -q pytest > /dev/null 2>&1; "
            "python3 -m pytest /tests/test_outputs.py -v"
        )
        run_cmd = [
            "docker", "run", "--rm",
            "--network", "host",
            *task_env_args,
            "-v", f"{solve_dir}:/solution:ro",
            "-v", f"{tests_dir}:/tests:ro",
            image_tag,
            "bash", "-c", verify_script,
        ]
    try:
        result = subprocess.run(run_cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        print(f"  Verification FAILED: docker run timed out after 600s")
        subprocess.run(["docker", "rmi", image_tag], capture_output=True)
        return False
    if result.returncode != 0:
        print(f"  Verification FAILED (exit {result.returncode}):")
        print(f"  stdout: {result.stdout[-500:]}")
        print(f"  stderr: {result.stderr[-500:]}")
        subprocess.run(["docker", "rmi", image_tag], capture_output=True)
        return False
    print("  solve.sh + test_outputs.py PASSED")

    subprocess.run(["docker", "rmi", image_tag], capture_output=True)
    return True


async def async_main():
    os.environ.pop("CLAUDECODE", None)

    parser = argparse.ArgumentParser(description="Generate training variants for SkillsBench tasks")
    parser.add_argument("--task", type=str, help="Single task to generate")
    parser.add_argument("--all", action="store_true", help="Generate all non-A-category tasks")
    parser.add_argument("--dry-run-only", action="store_true", help="Only verify existing variants")
    parser.add_argument("--skip-verify", action="store_true", help="Skip dry-run verification")
    parser.add_argument("--model", default="claude-opus-4-6", help="Model for generation agent")
    parser.add_argument("--max-budget", type=float, default=5.0, help="Max budget per task in USD")
    parser.add_argument("--force", action="store_true", help="Regenerate even if variant exists")
    args = parser.parse_args()

    if args.task:
        tasks = [args.task]
    elif args.all:
        tasks = sorted([
            d.name for d in TASKS_DIR.iterdir()
            if d.is_dir() and d.name not in SKIP_TASKS
        ])
    else:
        parser.error("Specify --task or --all")

    TASKS_TRAIN_DIR.mkdir(parents=True, exist_ok=True)

    results = {"pass": [], "fail": [], "skip": [], "shared_data": []}

    for task_name in tasks:
        print(f"\n{'='*60}")
        print(f"Task: {task_name}")
        strategy = get_strategy(task_name)
        print(f"Strategy: {strategy}")

        output_dir = TASKS_TRAIN_DIR / task_name

        if args.dry_run_only:
            if output_dir.exists():
                ok = verify_variant(task_name)
                results["pass" if ok else "fail"].append(task_name)
            else:
                print("  No variant exists, skipping")
                results["skip"].append(task_name)
            continue

        if output_dir.exists() and not args.force:
            print(f"  Training variant already exists, skipping (use --force to regenerate)")
            results["skip"].append(task_name)
            continue

        if output_dir.exists() and args.force:
            shutil.rmtree(output_dir)

        # Write strategy metadata for downstream reporting
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / ".strategy").write_text(strategy)

        ok = await run_generation_agent(
            task_name=task_name,
            strategy=strategy,
            output_dir=output_dir,
            model=args.model,
            max_budget=args.max_budget,
        )

        if ok and not args.skip_verify:
            verified = verify_variant(task_name)
            results["pass" if verified else "fail"].append(task_name)
        elif ok:
            results["pass"].append(task_name)
        else:
            results["fail"].append(task_name)

        if strategy == "subtask_split":
            results["shared_data"].append(task_name)

    # Summary
    print(f"\n{'='*60}")
    print("Generation Summary")
    print(f"  Pass: {len(results['pass'])}")
    print(f"  Fail: {len(results['fail'])}")
    print(f"  Skip: {len(results['skip'])}")
    print(f"  Shared-data (report separately): {len(results['shared_data'])}")
    if results["fail"]:
        print(f"  Failed tasks: {', '.join(results['fail'])}")
    if results["shared_data"]:
        print(f"  Shared-data tasks: {', '.join(results['shared_data'])}")

    # Write results log
    log_path = PROJECT_ROOT / "scripts" / "train_variant_results.json"
    log_path.write_text(json.dumps(results, indent=2))
    print(f"  Results log: {log_path}")


def main():
    anyio.run(async_main)


if __name__ == "__main__":
    main()
