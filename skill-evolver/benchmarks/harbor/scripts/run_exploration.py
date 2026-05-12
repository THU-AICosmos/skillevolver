"""
run_exploration.py — Harbor multi-trial runner with raw-reward ranking.

Helper module imported by run_and_wait.py. Not intended to be invoked as __main__
from the new skill-evolver location.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Project root is four levels up from skill-evolver/benchmarks/harbor/scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from agent.config import DEFAULT_MODEL, DEFAULT_N_ATTEMPTS, SKILLSBENCH_ROOT


def _resolve_signal_mode(raw_rewards: list[tuple[Optional[Path], float]]) -> str:
    requested = os.environ.get("SKILLSBENCH_REWARD_SIGNAL_MODE", "auto").strip().lower()
    if requested in {"continuous", "discrete"}:
        return requested

    # auto: keep discrete semantics only when rewards are truly binary.
    vals = [rv for _tp, rv in raw_rewards]
    if vals and all(rv in (0.0, 1.0) for rv in vals):
        return "discrete"
    return "continuous"


def collect_trial_results(job_dir: Path) -> dict:
    """Walk a Harbor job directory, read reward.txt per trial, find .jsonl transcripts.

    Harbor job directory structure::

        jobs/<job-name>/
          <task>__<7char>/           # trial dir
            verifier/
              reward.txt             # contains "0" or "1"
            agent/sessions/projects/-root/
              <session-uuid>.jsonl   # transcript
          <task>__<7char>/           # another trial
            ...

    Returns
    -------
    dict with keys:
        n_passed          (int) — threshold-based pass count
        n_failed          (int) — threshold-based fail count
        passed_transcripts (list[Path])  — absolute paths to .jsonl files (reward > threshold)
        failed_transcripts (list[Path])  — absolute paths (reward <= threshold)
        raw_rewards       (list[tuple[Path, float]]) — every trial's (transcript, raw_float_reward)
                          including partial-credit trials. Used by collect_and_preprocess to
                          compute mean_reward without losing fractional credit on tasks like
                          crystallographic-wyckoff (rewards 0.82, 0.89) or find-topk (0.5).

    Pass threshold is configurable via SKILLSBENCH_PASS_REWARD_MIN (default: 0.0).
    This allows tasks with fractional or >1 rewards to still contribute positive traces
    without requiring exact equality to 1.
    """
    passed_transcripts: list[Path] = []
    failed_transcripts: list[Path] = []
    raw_rewards: list[tuple[Optional[Path], float]] = []
    pass_reward_min_raw = os.environ.get("SKILLSBENCH_PASS_REWARD_MIN", "0.0")
    try:
        pass_reward_min = float(pass_reward_min_raw)
    except ValueError:
        pass_reward_min = 0.0

    for trial_dir in sorted(job_dir.iterdir()):
        if not trial_dir.is_dir():
            continue

        reward_file = trial_dir / "verifier" / "reward.txt"
        if not reward_file.exists():
            continue

        reward_text = reward_file.read_text(encoding="utf-8").strip()
        try:
            reward = float(reward_text)
        except ValueError:
            continue

        # Find .jsonl transcript(s) under agent/sessions/projects/{-root,-app}/
        # Exclude subagent traces (subagents/ subdirectory)
        transcripts: list[Path] = []
        projects_dir = trial_dir / "agent" / "sessions" / "projects"
        if projects_dir.exists():
            transcripts = sorted(
                p for p in projects_dir.rglob("*.jsonl")
                if "subagents" not in p.parts
            )

        # Use only the first (or only) transcript per trial
        transcript: Optional[Path] = transcripts[0].resolve() if transcripts else None

        # Always record the raw float reward for mean_reward computation
        raw_rewards.append((transcript, reward))

        if reward > pass_reward_min:
            if transcript is not None:
                passed_transcripts.append(transcript)
        else:
            if transcript is not None:
                failed_transcripts.append(transcript)

    signal_mode = _resolve_signal_mode(raw_rewards)

    return {
        "n_passed": len(passed_transcripts),
        "n_failed": len(failed_transcripts),
        "passed_transcripts": passed_transcripts,
        "failed_transcripts": failed_transcripts,
        "raw_rewards": raw_rewards,
        "pass_reward_min": pass_reward_min,
        "signal_mode": signal_mode,
    }


def pick_winner_loser(results: dict) -> tuple[Path, Path] | None:
    """Pick representative high/low transcripts for trace analysis.

    Returns
    -------
    tuple[Path, Path]
        (winner_transcript, loser_transcript) or None if impossible.
        Selection is based on raw reward, not the threshold-binarized pass bit.
    """
    signal_mode = results.get("signal_mode", "continuous")

    if signal_mode == "discrete":
        passed = [
            (tp, rv)
            for tp, rv in results.get("raw_rewards", [])
            if tp is not None and tp in set(results.get("passed_transcripts", []))
        ]
        failed = [
            (tp, rv)
            for tp, rv in results.get("raw_rewards", [])
            if tp is not None and tp in set(results.get("failed_transcripts", []))
        ]
        if not passed or not failed:
            return None
        passed.sort(key=lambda item: item[1], reverse=True)
        failed.sort(key=lambda item: item[1])
        return (passed[0][0], failed[0][0])

    ranked = [
        (tp, rv)
        for tp, rv in results.get("raw_rewards", [])
        if tp is not None
    ]
    if len(ranked) < 2:
        return None

    ranked.sort(key=lambda item: item[1], reverse=True)
    winner = ranked[0][0]
    loser = ranked[-1][0]
    return (winner, loser)


def run_exploration(
    task_name: str,
    n_attempts: int = DEFAULT_N_ATTEMPTS,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Run Harbor via subprocess for a task N times, return exploration results.

    Calls::

        uv run harbor run -p tasks-no-skills/<task> -a claude-code \\
            -m anthropic/<model> -k <n_attempts>

    After Harbor finishes, finds the most recent matching job dir, collects
    trial results, picks winner/loser, saves exploration.json, and returns
    the results dict.

    Parameters
    ----------
    task_name:
        Name of the SkillsBench task (subdirectory of tasks-no-skills/).
    n_attempts:
        Number of Harbor trial runs.
    model:
        Short model name (without ``anthropic/`` prefix).

    Returns
    -------
    dict with keys from collect_trial_results plus:
        job_dir     (str)  — path to Harbor job directory used
        winner      (str | None)  — absolute path to winner .jsonl
        loser       (str | None)  — absolute path to loser .jsonl
    """
    cmd = [
        "uv",
        "run",
        "harbor",
        "run",
        "-p",
        f"tasks-no-skills/{task_name}",
        "-a",
        "claude-code",
        "-m",
        f"anthropic/{model}",
        "-k",
        str(n_attempts),
    ]

    print(f"[run_exploration] Running Harbor: {' '.join(cmd)}", file=sys.stderr)
    subprocess.run(cmd, cwd=str(SKILLSBENCH_ROOT), check=True)

    # Find the most recent job directory matching the task name
    jobs_dir = SKILLSBENCH_ROOT / "jobs"
    matching_dirs = [
        d
        for d in jobs_dir.iterdir()
        if d.is_dir() and task_name in d.name
    ]
    if not matching_dirs:
        raise FileNotFoundError(
            f"No job directory found for task '{task_name}' under {jobs_dir}"
        )

    # Pick the most recently modified job dir
    job_dir = max(matching_dirs, key=lambda d: d.stat().st_mtime)
    print(f"[run_exploration] Job dir: {job_dir}", file=sys.stderr)

    results = collect_trial_results(job_dir)

    pair = pick_winner_loser(results)
    winner: Optional[Path] = pair[0] if pair is not None else None
    loser: Optional[Path] = pair[1] if pair is not None else None

    output = {
        "task": task_name,
        "n_attempts": n_attempts,
        "model": model,
        "job_dir": str(job_dir),
        "signal_mode": results.get("signal_mode", "continuous"),
        "pass_reward_min": results.get("pass_reward_min", 0.0),
        "n_passed": results["n_passed"],
        "n_failed": results["n_failed"],
        "passed_transcripts": [str(p) for p in results["passed_transcripts"]],
        "failed_transcripts": [str(p) for p in results["failed_transcripts"]],
        "winner": str(winner) if winner is not None else None,
        "loser": str(loser) if loser is not None else None,
    }

    exploration_json = job_dir / "exploration.json"
    exploration_json.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[run_exploration] Saved exploration.json → {exploration_json}", file=sys.stderr)

    return output


def _main():
    parser = argparse.ArgumentParser(
        description="Run Harbor N times for a task and pick winner/loser transcripts."
    )
    parser.add_argument("--task", required=True, help="SkillsBench task name")
    parser.add_argument(
        "--n-attempts",
        type=int,
        default=DEFAULT_N_ATTEMPTS,
        help=f"Number of Harbor trials (default: {DEFAULT_N_ATTEMPTS})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model short name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write results JSON (in addition to job dir)",
    )
    args = parser.parse_args()

    results = run_exploration(
        task_name=args.task,
        n_attempts=args.n_attempts,
        model=args.model,
    )

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main()
