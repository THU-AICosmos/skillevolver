"""
run_and_wait.py — Isolation boundary between skill-creator agent and Harbor.

The agent calls this script via Bash tool and only sees stdout + workspace files
— never raw Harbor data.

Usage:
    python scripts/run_and_wait.py \\
        --task X --phase exploration|validation \\
        --workspace /path --model M --n-attempts N \\
        [--skill-dir relative/path]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Project root is four levels up from skill-evolver/benchmarks/harbor/scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from agent.config import SKILLSBENCH_ROOT, TASKS_EVOLVED_SKILLS_DIR, TASKS_NO_SKILLS_DIR, HARBOR_TIMEOUT_MULTIPLIER

# Import siblings from same directory
_scripts_dir = str(Path(__file__).parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
from preprocess_trace import preprocess_trace, extract_metrics_from_jsonl
from run_exploration import collect_trial_results


def _clean_tasks_dir_skills(target_env: Path) -> None:
    """Remove `tasks-train/<task>/environment/skills/` entirely.

    The canonical state of a train variant is "no skills dir". Curated skills
    bundled with train variants are dead weight for the skill-evolver pipeline:
    Phase 2 overwrites `skills/` with strategy-hints before any trial runs, so
    trial agents never see the original content anyway. Keeping them around
    only invited bugs (crashed runs leaving strategy-hints behind, stale
    `skills.bak` promoted to canonical, the copy leaking into
    `train-context/`). We delete them at source instead, and this helper
    enforces the invariant before and after each exploration run.
    """
    current = target_env / "skills"
    if current.exists():
        shutil.rmtree(current)
    bak = target_env / "skills.bak"
    if bak.exists():
        shutil.rmtree(bak)


# ---------------------------------------------------------------------------
# deploy_skill_to_task_variant
# ---------------------------------------------------------------------------


def deploy_skill_to_task_variant(skill_dir: Path, task_variant_env: Path) -> None:
    """Deploy a skill directory to task_variant_env/skills/<name>/SKILL.md.

    Parameters
    ----------
    skill_dir:
        Directory that contains SKILL.md.  Its name is used as the named
        subdirectory under skills/ (Claude Code requires skills/<name>/SKILL.md,
        not skills/SKILL.md).
    task_variant_env:
        Path to the task-variant environment/ directory (the one with the
        Dockerfile).  Skills are written to task_variant_env/skills/.
    """
    skills_root = task_variant_env / "skills"

    # Clear any existing skills
    if skills_root.exists():
        shutil.rmtree(skills_root)
    skills_root.mkdir(parents=True)

    # skill_dir is like  iteration-1/skills/openpyxl-pivot-tables/
    # We copy it as a named subdirectory: skills/openpyxl-pivot-tables/
    dest = skills_root / skill_dir.name
    shutil.copytree(skill_dir, dest)

    skill_files = list(dest.rglob("*.md"))
    print(
        f"[deploy_skill_to_task_variant] Deployed {len(skill_files)} skill file(s) "
        f"to: {dest}",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# collect_and_preprocess
# ---------------------------------------------------------------------------


def collect_and_preprocess(
    job_dir: Path,
    workspace: Path,
    phase: str,
    write_traces: bool = True,
    requested_n_attempts: Optional[int] = None,
) -> dict:
    """Collect Harbor trial results, preprocess ALL traces, write to workspace.

    Writes:
        workspace/task/<phase>-traces/trial-01-pass.md  (for each trial)
        workspace/task/<phase>-results.json

    results.json schema::

        {
            "phase": "...",
            "n_passed": N,
            "n_failed": N,
            "n_attempts": N,
            "trials": [
                {
                    "id": "trial-01",
                    "reward": 1,
                    "total_tokens": ...,
                    "n_turns": ...,
                    "duration_seconds": ...,
                    "trace_file": "<phase>-traces/trial-01-pass.md"
                },
                ...
            ]
        }

    The results.json deliberately contains NO Harbor paths or job-directory
    references. The agent reads the trials table and picks which traces
    to analyze deeply.

    Parameters
    ----------
    job_dir:
        Path to a Harbor job directory (output of a harbor run).
    workspace:
        Root workspace directory; outputs go to workspace/task/.
    phase:
        Logical phase name (e.g. "exploration", "skill-test", "validation").

    Returns
    -------
    dict
        The results dict written to <phase>-results.json.
    """
    task_dir = workspace / "task"
    task_dir.mkdir(parents=True, exist_ok=True)

    traces_dir = task_dir / f"{phase}-traces"
    if write_traces:
        # Create traces directory (clean slate — parallel -k N writes all traces at once)
        if traces_dir.exists():
            shutil.rmtree(traces_dir)
        traces_dir.mkdir(parents=True)
    elif traces_dir.exists():
        shutil.rmtree(traces_dir)

    results = collect_trial_results(job_dir)
    passed_transcripts = results["passed_transcripts"]
    failed_transcripts = results["failed_transcripts"]
    raw_rewards = results.get("raw_rewards", [])
    signal_mode = results.get("signal_mode", "continuous")

    # Build a transcript -> raw float reward map for lookup.
    # passed/failed_transcripts carry threshold-binarized 0/1 labels, while
    # raw_reward preserves the original float for headline scoring.
    raw_by_path: dict[str, float] = {}
    for tpath, rval in raw_rewards:
        if tpath is not None:
            raw_by_path[str(tpath)] = rval

    passed_set = {str(p) for p in passed_transcripts}

    # Rank trials by raw reward so the agent sees strongest/weakest traces first.
    all_trials: list[tuple[Path, int, float]] = []
    for transcript_path, raw_reward in raw_rewards:
        if transcript_path is None:
            continue
        reward = 1 if str(transcript_path) in passed_set else 0
        all_trials.append((transcript_path, reward, raw_reward))
    all_trials.sort(key=lambda item: item[2], reverse=True)

    # Preprocess ALL traces and build trials array
    trials_meta: list[dict] = []
    for i, (transcript_path, reward, raw_reward) in enumerate(all_trials, start=1):
        trial_id = f"trial-{i:02d}"
        # `reward` here is the binarized 0/1 used for the trace label.
        # `raw_reward` preserves the original float (may be 0.0, 0.5, 0.89, 1.0, ...).
        raw_reward = raw_by_path.get(str(transcript_path), raw_reward)
        signal_label = "pass" if reward == 1 else "fail"
        trial_meta = {
            "id": trial_id,
            "reward": reward,
            "raw_reward": raw_reward,
            "rank": i,
            "signal_label": signal_label,
        }

        if write_traces:
            trace_filename = f"{trial_id}.md"
            trace_path = traces_dir / trace_filename

            # Preprocess trace to markdown
            try:
                preprocess_trace(str(transcript_path), reward=reward, output_path=str(trace_path))
            except Exception as e:
                print(f"  Warning: failed to preprocess {trial_id}: {e}", file=sys.stderr)
                continue
            trial_meta["trace_file"] = f"{phase}-traces/{trace_filename}"

        # Extract metrics
        try:
            metrics = extract_metrics_from_jsonl(str(transcript_path))
        except Exception:
            metrics = {"total_tokens": 0, "n_turns": 0, "duration_seconds": 0.0}

        trial_meta.update({
            "input_tokens": metrics.get("input_tokens", 0),
            "output_tokens": metrics.get("output_tokens", 0),
            "cache_read_tokens": metrics.get("cache_read_tokens", 0),
            "cache_creation_tokens": metrics.get("cache_creation_tokens", 0),
            "total_tokens": metrics.get("total_tokens", 0),
            "n_turns": metrics.get("n_turns", 0),
            "duration_seconds": metrics.get("duration_seconds", 0.0),
        })
        trials_meta.append(trial_meta)

    n_passed = results["n_passed"]
    n_failed = results["n_failed"]
    n_attempts = n_passed + n_failed

    # Compute mean_reward across all trials with the raw float reward.
    # Includes partial credit/fractional scores that binarized n_passed may
    # collapse. Computed against n_attempts so missing trials (e.g. infra-killed)
    # don't artificially inflate it.
    if raw_rewards and n_attempts > 0:
        # Use only rewards whose transcript made it into trials_meta
        # (some raw_rewards may have None transcript and got dropped above)
        raw_vals = [rv for tp, rv in raw_rewards if tp is not None]
        mean_reward = (sum(raw_vals) / n_attempts) if raw_vals else 0.0
    else:
        mean_reward = 0.0

    # Build results dict — NO Harbor paths
    output = {
        "phase": phase,
        "signal_mode": signal_mode,
        "pass_reward_min": results.get("pass_reward_min", 0.0),
        "n_passed": n_passed,
        "n_failed": n_failed,
        "n_attempts": n_attempts,
        "requested_n_attempts": requested_n_attempts,
        "mean_reward": round(mean_reward, 4),
        "trials": trials_meta,
    }

    results_path = task_dir / f"{phase}-results.json"
    results_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    return output


# ---------------------------------------------------------------------------
# run_and_wait
# ---------------------------------------------------------------------------


def run_and_wait(
    task_name: str,
    phase: str,
    workspace: Path,
    model: str,
    n_attempts: int,
    skill_dir: Optional[Path] = None,
    tmux_window: str = "harbor:0",
    tasks_dir: Optional[str] = None,
) -> dict:
    """Full flow: optionally deploy skill, run Harbor, collect + preprocess results.

    Parameters
    ----------
    task_name:
        SkillsBench task name.
    phase:
        One of "exploration" or "validation".
    workspace:
        Workspace root directory (agent-visible).
    model:
        Model name (e.g. "anthropic/claude-sonnet-4-6"); passed directly to Harbor
        automatically.
    n_attempts:
        Number of Harbor trials (-k flag).
    skill_dir:
        Path to a skill directory (containing SKILL.md) to deploy before running.
        Ignored if phase == "exploration" or if None.

    Returns
    -------
    dict
        The results dict from collect_and_preprocess.
    """
    # Step 1: Deploy skill if applicable
    _tasks_dir_target_env = None  # set only when deploying to a tasks_dir variant
    if skill_dir is not None:
        if tasks_dir:
            # Deploy skill directly to the tasks_dir variant (e.g. tasks-train/).
            # deploy_skill_to_task_variant already rmtree's and recreates
            # skills/, so no pre-deploy cleanup is needed here.
            target_env = SKILLSBENCH_ROOT / tasks_dir / task_name / "environment"
            _tasks_dir_target_env = target_env
            deploy_skill_to_task_variant(skill_dir, target_env)
        else:
            # Deploy to the evolved-skills task variant
            from agent.workspace import ensure_task_variant

            evolved_task_dir = TASKS_EVOLVED_SKILLS_DIR / task_name
            ensure_task_variant(task_name, evolved_task_dir)
            deploy_skill_to_task_variant(skill_dir, evolved_task_dir / "environment")

    # Step 2: Choose the Harbor task path
    if tasks_dir:
        # Explicit override — used for train/test split
        task_path = f"{tasks_dir}/{task_name}"
    elif skill_dir is None:
        task_path = f"tasks-no-skills/{task_name}"
    else:
        task_path = f"tasks-evolved-skills/{task_name}"

    proxy_exports: list[str] = []
    for key in (
        "http_proxy",
        "https_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
        "ANTHROPIC_API_KEY",
    ):
        value = os.environ.get(key)
        if value:
            proxy_exports.append(f"export {key}={json.dumps(value)}")

    proxy_prefix = ""
    if proxy_exports:
        proxy_prefix = " && ".join(proxy_exports) + " && "

    harbor_cmd = (
        f"{proxy_prefix}cd {SKILLSBENCH_ROOT} && "
        f"uv run harbor run -p {task_path} -a claude-code -m {model} -k {n_attempts}"
        f" -n {n_attempts}"  # match concurrency to trial count (default is 4, blocks 5-trial validation)
        f" --timeout-multiplier {HARBOR_TIMEOUT_MULTIPLIER}"
    )

    import time

    # Record timestamp before starting so we can find the new job dir
    start_time = time.time()
    jobs_dir = SKILLSBENCH_ROOT / "jobs"

    # Send Harbor command to the specified tmux window
    # Use explicit socket path to ensure subprocess can reach tmux
    tmux_socket = f"/tmp/tmux-{os.getuid()}/default"
    tmux_target = tmux_window

    print(f"Running {phase} for {task_name} ({n_attempts} attempts, {model})...")
    print(f"Sending Harbor command to tmux {tmux_target}...")

    # Reset the target pane before sending a new Harbor command. Without this,
    # partially typed input from a previous run can prefix the next command
    # (for example `sexport ...` instead of `export ...`) and silently break
    # orchestration while the outer poll loop waits for a job that never starts.
    subprocess.run(
        ["tmux", "-S", tmux_socket, "send-keys", "-t", tmux_target, "C-c"],
        check=True,
    )
    time.sleep(1)
    subprocess.run(
        ["tmux", "-S", tmux_socket, "send-keys", "-t", tmux_target, "Enter"],
        check=True,
    )
    time.sleep(1)
    subprocess.run(
        ["tmux", "-S", tmux_socket, "send-keys", "-t", tmux_target, "-l", harbor_cmd],
        check=True,
    )
    subprocess.run(
        ["tmux", "-S", tmux_socket, "send-keys", "-t", tmux_target, "Enter"],
        check=True,
    )

    # Poll for completion: wait for a new job dir with result.json
    # Match by task_name prefix in trial subdirectory names to avoid
    # picking up jobs from parallel runs of other tasks.
    print(f"Waiting for Harbor to complete...", flush=True)
    poll_deadline = start_time + (3 * 60 * 60)  # 3-hour hard cap
    finished_at_seen_at: Optional[float] = None
    while True:
        time.sleep(30)
        if time.time() > poll_deadline:
            raise TimeoutError(
                f"Timed out after 3 hours waiting for Harbor job for task {task_name}. "
                f"Check tmux window {tmux_window} and {jobs_dir} manually."
            )
        # Find job dirs created after we started
        if not jobs_dir.exists():
            print(".", end="", flush=True)
            continue
        new_dirs = [
            d for d in jobs_dir.iterdir()
            if d.is_dir() and d.stat().st_mtime > start_time
        ]
        if not new_dirs:
            print(".", end="", flush=True)
            continue

        # Check newest dirs for result.json, matching task name.
        # Harbor truncates trial names to task_name[:32] (see
        # harbor/models/trial/config.py generate_trial_name), so we must
        # match against the same truncation — otherwise long task names
        # like "crystallographic-wyckoff-position-analysis" never match
        # and the poll loop hangs until the 30-minute hard timeout.
        task_prefix = task_name[:32]
        for candidate in sorted(new_dirs, key=lambda d: d.stat().st_mtime, reverse=True):
            # Verify this job belongs to our task by checking trial dir names
            trial_dirs = [
                d for d in candidate.iterdir()
                if d.is_dir() and d.name.startswith(f"{task_prefix}__")
            ]
            if not trial_dirs:
                continue  # Wrong task — skip

            result_file = candidate / "result.json"
            if result_file.exists():
                # Verify trials have reward.txt (or at least result.json indicates completion)
                done_trials = [
                    d for d in trial_dirs
                    if (d / "verifier" / "reward.txt").exists()
                ]
                if len(done_trials) >= n_attempts:
                    break
                # If Harbor marked the job done but not all rewards have flushed,
                # give a 60-second grace period before accepting partial results.
                # This avoids the silent data-loss bug where Harbor errored or
                # timed out on some trials and we collect fewer than requested.
                try:
                    result_data = json.loads(result_file.read_text())
                    if result_data.get("finished_at"):
                        if finished_at_seen_at is None:
                            finished_at_seen_at = time.time()
                            print(
                                f"\n[run_and_wait] Harbor finished_at set with "
                                f"{len(done_trials)}/{n_attempts} trials done; "
                                f"waiting 60s for stragglers...",
                                flush=True,
                            )
                        elif time.time() - finished_at_seen_at >= 60:
                            print(
                                f"[run_and_wait] Grace period expired; accepting "
                                f"partial result with {len(done_trials)}/{n_attempts} trials.",
                                flush=True,
                            )
                            break
                except Exception:
                    pass
            continue
        else:
            # No matching job found yet
            print(".", end="", flush=True)
            continue
        break  # Found matching completed job

    job_dir = candidate
    print(f"\nHarbor completed. Job dir: {job_dir.name}")
    print(f"[run_and_wait] Job dir: {job_dir}", file=sys.stderr)

    # Step 4: Remove the strategy-hints skill we deployed to tasks-train.
    # Canonical state for a train variant is "no skills dir" — see
    # _clean_tasks_dir_skills for the rationale.
    if _tasks_dir_target_env is not None:
        _clean_tasks_dir_skills(_tasks_dir_target_env)
        print(f"[run_and_wait] Removed {_tasks_dir_target_env / 'skills'}", file=sys.stderr)

    # Step 5: Collect and preprocess
    results = collect_and_preprocess(
        job_dir=job_dir,
        workspace=workspace,
        phase=phase,
        write_traces=(phase != "validation"),
        requested_n_attempts=n_attempts,
    )

    # Step 6: If exploration with train/test split, copy train context to workspace
    if phase == "exploration" and tasks_dir:
        from agent.workspace import copy_train_context
        copy_train_context(task_name, workspace)

    # Step 7: Print summary
    n_passed = results["n_passed"]
    n_attempts_actual = results["n_attempts"]
    if n_attempts_actual != n_attempts:
        # Stdout (not stderr) so the agent's bash capture forwards it reliably
        print(
            f"WARNING: requested {n_attempts} trials but only collected {n_attempts_actual}. "
            f"Some Harbor trials may have errored before writing reward.txt. "
            f"Check job dir: {job_dir}"
        )
    print(
        f"Done. {n_passed}/{n_attempts_actual} passed (requested {n_attempts}). "
        f"Results saved to {workspace / 'task'}/"
    )

    # Validation phase: signal pipeline completion so run.py kills the session.
    # This prevents the agent from reading traces and debugging after validation.
    if phase == "validation":
        print("\nPIPELINE COMPLETE")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main():
    parser = argparse.ArgumentParser(
        description=(
            "Isolation boundary between skill-creator agent and Harbor. "
            "Runs Harbor, collects and preprocesses results into workspace."
        )
    )
    parser.add_argument("--task", required=True, help="SkillsBench task name")
    parser.add_argument(
        "--phase",
        required=True,
        choices=["exploration", "validation"],
        help="Pipeline phase",
    )
    parser.add_argument(
        "--workspace",
        required=True,
        type=Path,
        help="Workspace root directory (agent-visible output)",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model name (e.g. anthropic/claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--n-attempts",
        type=int,
        required=True,
        help="Number of Harbor trials",
    )
    parser.add_argument(
        "--skill-dir",
        type=str,
        default=None,
        help="Skill directory (relative to --workspace) to deploy before running.",
    )
    parser.add_argument(
        "--tasks-dir",
        type=str,
        default=None,
        help="Override Harbor task directory (e.g. 'tasks-train' for exploration with train/test split)",
    )
    parser.add_argument(
        "--tmux-window",
        type=str,
        default="harbor:0",
        help="Tmux target window for Harbor commands (default: harbor:0)",
    )
    args = parser.parse_args()

    workspace = args.workspace
    if not workspace.is_absolute():
        workspace = Path.cwd() / workspace

    skill_dir: Optional[Path] = None
    if args.skill_dir:
        skill_dir = workspace / args.skill_dir
        if not skill_dir.exists():
            print(f"ERROR: --skill-dir does not exist: {skill_dir}", file=sys.stderr)
            sys.exit(1)

    run_and_wait(
        task_name=args.task,
        phase=args.phase,
        workspace=workspace,
        model=args.model,
        n_attempts=args.n_attempts,
        skill_dir=skill_dir,
        tmux_window=args.tmux_window,
        tasks_dir=args.tasks_dir,
    )


if __name__ == "__main__":
    _main()
