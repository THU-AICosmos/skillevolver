"""aggregate_results.py — Results aggregation pipeline for self-evolving skills.

Tasks 1-6: parse baselines, load analyses, discover tasks, build JSONL records,
generate markdown report, CLI interface.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVOLVED_SKILLS_DIR = PROJECT_ROOT / "evolved-skills"
CATEGORIZATION_FILE = PROJECT_ROOT / "docs" / "task_list" / "task-categorization-o46-s45.md"
ANALYSIS_DIR = PROJECT_ROOT / "docs" / "task_list" / "analysis"
JSONL_OUTPUT = PROJECT_ROOT / "docs" / "task_list" / "results-db.jsonl"
REPORT_OUTPUT = PROJECT_ROOT / "docs" / "task_list" / "report.md"
DETAIL_OUTPUT = PROJECT_ROOT / "docs" / "task_list" / "per-task-analysis.md"

SKIP_DIRS = {"former"}

# Known pipeline version directories — these are NOT task slugs, they are the
# top-level bucket under evolved-skills/. Layout:
# evolved-skills/<version>/<task>/<timestamp>/.
KNOWN_VERSIONS = {"evolver"}


def _has_exploration_results(ts_dir: Path) -> bool:
    """Check if this timestamp dir has exploration results (old or new naming)."""
    task_dir = ts_dir / "task"
    if (task_dir / "exploration-results.json").exists():
        return True
    # Unified explore loop writes exploration-k<N>-results.json. Accept any k index.
    if any(task_dir.glob("exploration-k*-results.json")):
        return True
    # Legacy name ordering (never shipped, but keep for safety)
    if (task_dir / "exploration-results-k0.json").exists():
        return True
    return False


# ---------------------------------------------------------------------------
# Task 1: Baseline Parser
# ---------------------------------------------------------------------------

_TASK_ROW_RE = re.compile(r"^\|\s*(?P<task>[a-z0-9][\w-]+)\s*\|")


def parse_baselines(path: Path = CATEGORIZATION_FILE) -> dict[str, dict]:
    """Parse task-categorization-o46-s45.md into {task: {domain, o46_no, s45_no, o46_with, s45_with}}."""
    text = path.read_text(encoding="utf-8")
    result: dict[str, dict] = {}

    for line in text.splitlines():
        m = _TASK_ROW_RE.match(line)
        if not m:
            continue
        # Split on | and strip
        parts = [p.strip() for p in line.split("|")]
        # parts[0] is empty (before first |), parts[1]=task, parts[2]=domain,
        # parts[3]=o46_no, parts[4]=s45_no, parts[5]=o46_with, parts[6]=s45_with,
        # parts[7]=delta_o46, parts[8]=delta_s45
        if len(parts) < 8:
            continue
        task = parts[1].strip()
        domain = parts[2].strip()
        try:
            o46_no = float(parts[3])
            s45_no = float(parts[4])
            o46_with = float(parts[5])
            s45_with = float(parts[6])
        except (ValueError, IndexError):
            continue
        result[task] = {
            "domain": domain,
            "o46_no": o46_no,
            "s45_no": s45_no,
            "o46_with": o46_with,
            "s45_with": s45_with,
        }

    return result


# ---------------------------------------------------------------------------
# Task 2: Analysis File Frontmatter Parser
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)
_YAML_LINE_RE = re.compile(r'^(\w+):\s*"?([^"\n]+)"?\s*$')


def parse_analysis_file(content: str) -> tuple[dict, str]:
    """Parse frontmatter + body from markdown content.

    Returns (meta_dict, body_str). If no frontmatter, returns ({}, content).
    """
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return {}, content

    frontmatter_text = m.group(1)
    body = m.group(2)

    meta: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        ym = _YAML_LINE_RE.match(line)
        if ym:
            meta[ym.group(1)] = ym.group(2).strip()

    return meta, body


def load_all_analyses(directory: Path) -> dict[str, dict]:
    """Load all .md analysis files from directory, skip files starting with '_'.

    Returns {slug: {meta, body}}.
    """
    result: dict[str, dict] = {}
    if not directory.is_dir():
        return result

    for md_file in sorted(directory.glob("*.md")):
        if md_file.name.startswith("_"):
            continue
        slug = md_file.stem
        content = md_file.read_text(encoding="utf-8")
        meta, body = parse_analysis_file(content)
        result[slug] = {"meta": meta, "body": body}

    return result


# ---------------------------------------------------------------------------
# Task 3: Task Discovery + JSON Data Loading
# ---------------------------------------------------------------------------


def discover_tasks(
    evolved_skills_dir: Path = EVOLVED_SKILLS_DIR,
    version: str = "evolver",
) -> dict[str, Path]:
    """Walk ``evolved-skills/<version>/``, return ``{task_slug: latest_ts_dir}``.

    Picks the latest timestamp per task that has a full pipeline run
    (exploration results present). Falls back to legacy
    ``result.json``-only runs only when no full run exists for that task.

    Layout: ``evolved-skills/<version>/<task>/<timestamp>/``. ``version`` is
    recorded in the path because a single task can have runs from multiple
    pipeline and the old
    "latest-timestamp-wins" flat layout was silently clobbering cross-pipeline
    data.
    """
    result: dict[str, Path] = {}
    version_dir = evolved_skills_dir / version
    if not version_dir.is_dir():
        return result

    for task_dir in sorted(version_dir.iterdir()):
        if not task_dir.is_dir():
            continue
        if task_dir.name in SKIP_DIRS:
            continue

        # Find all timestamp subdirs
        ts_dirs = sorted(
            [d for d in task_dir.iterdir() if d.is_dir() and _looks_like_timestamp(d.name)],
            key=lambda d: d.name,
        )
        if not ts_dirs:
            continue

        # Pick the latest timestamp that has exploration results (full pipeline run).
        # No-trace runs don't have exploration results — they should NOT be picked here.
        chosen = None
        for ts_dir in reversed(ts_dirs):
            if _has_exploration_results(ts_dir):
                chosen = ts_dir
                break

        # Fallback: legacy runs may only have result.json. Only use this if no full run found.
        if chosen is None:
            for ts_dir in reversed(ts_dirs):
                if (ts_dir / "result.json").exists() and not (ts_dir / "task" / "validation-results.json").exists():
                    # Legacy result.json without separate phase files — accept it
                    chosen = ts_dir
                    break

        if chosen:
            result[task_dir.name] = chosen

    return result


def discover_notrace_runs(
    evolved_skills_dir: Path = EVOLVED_SKILLS_DIR,
    version: str = "notrace",
) -> dict[str, Path]:
    """Walk ``evolved-skills/<version>/``, return ``{slug: latest_notrace_ts_dir}``.

    A no-trace run is identified by having ``task/validation-results.json``
    but NOT exploration results — these are the condition-D
    ablation runs.
    """
    result: dict[str, Path] = {}
    version_dir = evolved_skills_dir / version
    if not version_dir.is_dir():
        return result

    for task_dir in sorted(version_dir.iterdir()):
        if not task_dir.is_dir():
            continue
        if task_dir.name in SKIP_DIRS:
            continue

        ts_dirs = sorted(
            [d for d in task_dir.iterdir() if d.is_dir() and _looks_like_timestamp(d.name)],
            key=lambda d: d.name,
        )
        if not ts_dirs:
            continue

        chosen = None
        for ts_dir in reversed(ts_dirs):
            has_exp = _has_exploration_results(ts_dir)
            has_val = (ts_dir / "task" / "validation-results.json").exists()
            if has_val and not has_exp:
                chosen = ts_dir
                break

        if chosen:
            result[task_dir.name] = chosen

    return result


def _looks_like_timestamp(name: str) -> bool:
    """Check if name looks like YYYYMMDD_HHMMSS."""
    return bool(re.match(r"^\d{8}_\d{6}$", name))


def _parse_phase(phase_data: dict) -> dict:
    """Normalize a phase dict: rename keys, compute aggregates."""
    if not phase_data:
        return {}

    trials_raw = phase_data.get("trials", [])
    trials_normalized = []
    for t in trials_raw:
        tn = dict(t)
        # Rename keys
        if "n_turns" in tn:
            tn["turns"] = tn.pop("n_turns")
        if "total_tokens" in tn:
            tn["tokens"] = tn.pop("total_tokens")
        if "duration_seconds" in tn:
            tn["duration"] = tn.pop("duration_seconds")
        trials_normalized.append(tn)

    n_passed = phase_data.get("n_passed", 0)
    n_failed = phase_data.get("n_failed", 0)
    n_attempts = phase_data.get("n_attempts", len(trials_raw))

    # Compute averages from trials if not in top-level
    turns_list = [t["turns"] for t in trials_normalized if "turns" in t]
    tokens_list = [t["tokens"] for t in trials_normalized if "tokens" in t]
    duration_list = [t["duration"] for t in trials_normalized if "duration" in t]

    avg_turns = statistics.mean(turns_list) if turns_list else phase_data.get("avg_turns")
    avg_tokens = statistics.mean(tokens_list) if tokens_list else phase_data.get("avg_tokens")
    avg_duration = statistics.mean(duration_list) if duration_list else phase_data.get("avg_duration_seconds")

    # Cost
    cost_usd = phase_data.get("estimated_cost_usd") or phase_data.get("cost_usd")

    # Raw reward: phase-level mean + per-trial raw values
    # raw_reward preserves the fractional score (0.833, 0.94) that the binary
    # pass/fail metric discards. Critical for distinguishing near-pass from
    # complete failure — a 0/5 skill with mean_reward=0.94 is very different
    # from a 0/5 skill with mean_reward=0.0.
    mean_reward = phase_data.get("mean_reward")
    if mean_reward is None and trials_raw:
        raw_vals = [t.get("raw_reward") for t in trials_raw if t.get("raw_reward") is not None]
        mean_reward = round(sum(raw_vals) / len(raw_vals), 4) if raw_vals else None

    return {
        "pass": n_passed,
        "fail": n_failed,
        "attempts": n_attempts,
        "mean_reward": mean_reward,
        "avg_turns": avg_turns,
        "avg_tokens": avg_tokens,
        "avg_duration": avg_duration,
        "cost_usd": cost_usd,
        "trials": trials_normalized,
    }


def audit_oracle_reads(ts_dir: Path) -> dict:
    """Scan agent.log for evidence that the skill-creator agent read the
    training-task ground truth (`train-context/solution/solve.sh` or
    `train-context/tests/test_outputs.py`).

    This is the post-hoc oracle-leak audit. For tasks where condition C
    beats condition A *and* the agent never read the oracle, the lift is
    demonstrably not from training-oracle leakage — which is the cheapest
    rebuttal to the "you're just leaking the oracle" critique.

    Catches both Tool-call reads (`Read` tool) and shell reads
    (`cat`, `head`, `less`, `tail`, `view`, `grep`) by substring-matching
    the canonical paths in the log.
    """
    log_path = ts_dir / "agent.log"
    audit = {
        "agent_log_present": False,
        "read_solve_sh": False,
        "read_test_outputs": False,
        "read_train_skill": False,
        "any_oracle_read": False,
    }
    if not log_path.exists():
        return audit

    audit["agent_log_present"] = True
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return audit

    # Substring matching is sufficient — the path is unique enough that any
    # appearance in the log (Read tool input or Bash command) indicates access.
    if "train-context/solution/solve.sh" in text or "train-context/solution/" in text:
        audit["read_solve_sh"] = True
    if "train-context/tests/test_outputs.py" in text:
        audit["read_test_outputs"] = True
    if "train-context/environment/skills/" in text:
        audit["read_train_skill"] = True

    audit["any_oracle_read"] = (
        audit["read_solve_sh"]
        or audit["read_test_outputs"]
        or audit["read_train_skill"]
    )
    return audit


def load_task_data(ts_dir: Path) -> dict:
    """Load task data from a timestamp directory.

    Reads result.json (preferred) or exploration-results{-k0}.json + validation-results.json.
    Also runs the oracle-peek audit on agent.log.
    """
    timestamp = None
    total_cost_usd = None
    exploration = None
    validation = None
    version = None

    result_json = ts_dir / "result.json"
    if result_json.exists():
        data = json.loads(result_json.read_text(encoding="utf-8"))
        timestamp = data.get("timestamp")
        total_cost_usd = data.get("harbor_cost_usd")
        version = data.get("version")
        phases = data.get("phases", {})
        if "exploration" in phases:
            exploration = _parse_phase(phases["exploration"])
        if "validation" in phases:
            validation = _parse_phase(phases["validation"])

    # Always check task/ subdirectory files — they may have richer data
    # than result.json (which sometimes has zeroed phases)
    exp_file = ts_dir / "task" / "exploration-results.json"
    if not exp_file.exists():
        # Unified explore loop writes exploration-k<N>-results.json — pick k=0
        k0_file = ts_dir / "task" / "exploration-k0-results.json"
        if k0_file.exists():
            exp_file = k0_file
        else:
            # Legacy ordering (never shipped)
            exp_file = ts_dir / "task" / "exploration-results-k0.json"
    val_file = ts_dir / "task" / "validation-results.json"
    if exp_file.exists():
        exp_from_file = _parse_phase(json.loads(exp_file.read_text(encoding="utf-8")))
        # Use file data if result.json had empty/zero attempts
        if exploration is None or exploration.get("attempts", 0) == 0:
            exploration = exp_from_file
    if val_file.exists():
        val_from_file = _parse_phase(json.loads(val_file.read_text(encoding="utf-8")))
        if validation is None or validation.get("attempts", 0) == 0:
            validation = val_from_file
        elif validation.get("mean_reward") is None and val_from_file.get("mean_reward") is not None:
            # result.json lacks mean_reward — backfill from validation-results.json.
            # result.json's validation phase was added before raw_reward tracking;
            # validation-results.json always has it. Same for trials (raw_reward per trial).
            validation["mean_reward"] = val_from_file["mean_reward"]
            if val_from_file.get("trials"):
                validation["trials"] = val_from_file["trials"]

    return {
        "timestamp": timestamp,
        "total_cost_usd": total_cost_usd,
        "version": version,
        "exploration": exploration,
        "validation": validation,
        "oracle_audit": audit_oracle_reads(ts_dir),
    }


# ---------------------------------------------------------------------------
# Task 4: JSONL Builder
# ---------------------------------------------------------------------------

_OUTCOME_ORDER = {"success": 0, "partial": 1, "fail": 2, "incomplete": 3}


def _compute_efficiency(task_data: dict, baseline: dict | None) -> dict:
    """Compute efficiency metrics comparing exploration vs validation phases."""
    exp = task_data.get("exploration") or {}
    val = task_data.get("validation") or {}

    exp_turns = exp.get("avg_turns")
    val_turns = val.get("avg_turns")
    exp_tokens = exp.get("avg_tokens")
    val_tokens = val.get("avg_tokens")

    # turn_delta = validation - exploration
    turn_delta = None
    if exp_turns is not None and val_turns is not None:
        turn_delta = round(val_turns - exp_turns, 2)

    # token_delta_pct
    token_delta_pct = None
    if exp_tokens and val_tokens:
        token_delta_pct = round((val_tokens - exp_tokens) / exp_tokens * 100, 1)

    # duration_delta_pct
    exp_dur = exp.get("avg_duration")
    val_dur = val.get("avg_duration")
    duration_delta_pct = None
    if exp_dur and val_dur:
        duration_delta_pct = round((val_dur - exp_dur) / exp_dur * 100, 1)

    # evolved_pass_rate
    evolved_pass_rate = None
    if val and val.get("attempts"):
        evolved_pass_rate = round(val["pass"] / val["attempts"], 3)

    # evolved_mean_reward: the fractional reward (e.g. 0.94 on a 0/5 binary-fail task)
    # Distinguishes near-pass failures from complete failures. Critical on tasks with
    # strict binary thresholds (e.g. trend-anomaly's <20% extreme assertion at 20.6%).
    evolved_mean_reward = val.get("mean_reward") if val else None

    # curated_pass_rate
    curated_pass_rate = None
    if baseline:
        curated_pass_rate = baseline.get("o46_with")

    # evolved_vs_curated classification
    evolved_vs_curated = "no_data"
    if evolved_pass_rate is not None and curated_pass_rate is not None:
        if evolved_pass_rate <= 0.2 and curated_pass_rate <= 0.2:
            evolved_vs_curated = "both_fail"
        elif evolved_pass_rate > curated_pass_rate:
            evolved_vs_curated = "evolved_gt_curated"
        elif evolved_pass_rate >= curated_pass_rate:
            evolved_vs_curated = "evolved_ge_curated"
        else:
            evolved_vs_curated = "evolved_lt_curated"
    elif evolved_pass_rate is None:
        evolved_vs_curated = "no_data"

    return {
        "turn_delta": turn_delta,
        "token_delta_pct": token_delta_pct,
        "duration_delta_pct": duration_delta_pct,
        "evolved_pass_rate": evolved_pass_rate,
        "evolved_mean_reward": evolved_mean_reward,
        "curated_pass_rate": curated_pass_rate,
        "evolved_vs_curated": evolved_vs_curated,
    }


def build_record(
    task_slug: str,
    task_data: dict,
    baseline: dict | None,
    analysis_meta: dict | None,
) -> dict:
    """Build a single result record dict."""
    meta = analysis_meta or {}

    skill = meta.get("skill")
    category = meta.get("category")
    notes = meta.get("notes")

    # Outcome: prefer frontmatter override, otherwise derive from C vs B numbers.
    outcome = meta.get("outcome")
    if not outcome:
        val = task_data.get("validation") or {}
        v_att = val.get("attempts", 0) or 0
        v_pass = val.get("pass", 0) or 0
        if v_att == 0:
            outcome = "incomplete"
        else:
            c_rate = v_pass / v_att
            b_rate = (baseline or {}).get("o46_with")
            if b_rate is None:
                outcome = "success" if c_rate >= 0.6 else ("partial" if c_rate >= 0.2 else "fail")
            elif c_rate >= b_rate:
                outcome = "success"
            elif c_rate >= b_rate - 0.2:
                outcome = "partial"
            else:
                outcome = "fail"

    record: dict[str, Any] = {
        "task": task_slug,
        "domain": baseline["domain"] if baseline else None,
        "category": category,
        "outcome": outcome,
        "skill": skill,
        "notes": notes,
        "timestamp": task_data.get("timestamp"),
        "total_cost_usd": task_data.get("total_cost_usd"),
        "version": task_data.get("version"),
        # Baseline
        "o46_no": baseline["o46_no"] if baseline else None,
        "s45_no": baseline["s45_no"] if baseline else None,
        "o46_with": baseline["o46_with"] if baseline else None,
        "s45_with": baseline["s45_with"] if baseline else None,
        # Phases
        "exploration": task_data.get("exploration"),
        "validation": task_data.get("validation"),
        # Efficiency
        "efficiency": _compute_efficiency(task_data, baseline),
        # Oracle peek audit (post-hoc anti-leak check)
        "oracle_audit": task_data.get("oracle_audit"),
    }

    return record


# ---------------------------------------------------------------------------
# Task 5: Report Generator
# ---------------------------------------------------------------------------

_OUTCOME_ICON = {
    "success": "✅",
    "partial": "⚠️",
    "fail": "✗",
    "incomplete": "⚠️ pipeline incomplete",
}


def _fmt_phase(phase: dict | None) -> str:
    if not phase:
        return "—"
    return f"{phase['pass']}/{phase['attempts']}"


def _fmt_tokens(n: int | float | None) -> str:
    if n is None:
        return "—"
    if n == 0:
        return "0"
    n = int(n)
    if n >= 1_000_000:
        val = n / 1_000_000
        # Format: remove trailing zeros but keep up to 2 decimal places
        formatted = f"{val:.2f}".rstrip("0").rstrip(".")
        return f"{formatted}M"
    elif n >= 1_000:
        val = n / 1_000
        formatted = f"{val:.0f}"
        return f"{formatted}k"
    return str(n)


def _fmt_float(v: float | None, decimals: int = 1) -> str:
    if v is None:
        return "—"
    return f"{v:.{decimals}f}"


def generate_report(
    records: list[dict],
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    # Header
    lines.append(f"<!-- AUTO-GENERATED by scripts/aggregate_results.py on {now} — DO NOT EDIT MANUALLY -->")
    lines.append("")
    lines.append("# Self-Evolving Skills — Results Report")
    lines.append("")

    # -----------------------------------------------------------------------
    # Summary table
    # -----------------------------------------------------------------------
    lines.append("## Summary")
    lines.append("")

    n_success = sum(1 for r in records if r["outcome"] == "success")
    n_total = len(records)
    lines.append(f"**Overall: {n_success} improved / {n_total} completed**")
    lines.append("")

    lines.append("| # | Task | Cat | Domain | Exploration | Validation | Skill | Outcome |")
    lines.append("|---|------|-----|--------|:-----------:|:----------:|-------|---------|")
    for i, rec in enumerate(records, 1):
        icon = _OUTCOME_ICON.get(rec["outcome"], rec["outcome"])
        skill = rec.get("skill") or "—"
        cat = rec.get("category") or "—"
        domain = rec.get("domain") or "—"
        lines.append(
            f"| {i} | {rec['task']} | {cat} | {domain} "
            f"| {_fmt_phase(rec.get('exploration'))} "
            f"| {_fmt_phase(rec.get('validation'))} "
            f"| {skill} | {icon} |"
        )
    lines.append("")

    # -----------------------------------------------------------------------
    # Harbor Trial Metrics
    # -----------------------------------------------------------------------
    lines.append("## Harbor Trial Metrics")
    lines.append("")

    lines.append("### Exploration Phase (no skill)")
    lines.append("")
    lines.append("| Task | Pass | Avg Turns | Avg Duration | Avg Tokens |")
    lines.append("|------|:----:|:---------:|:------------:|:----------:|")
    for rec in records:
        exp = rec.get("exploration")
        if exp:
            lines.append(
                f"| {rec['task']} "
                f"| {_fmt_phase(exp)} "
                f"| {_fmt_float(exp.get('avg_turns'))} "
                f"| {_fmt_float(exp.get('avg_duration'))}s "
                f"| {_fmt_tokens(exp.get('avg_tokens'))} |"
            )
    lines.append("")

    lines.append("### Validation Phase (with evolved skill)")
    lines.append("")
    lines.append("| Task | Pass | Avg Turns | Avg Duration | Avg Tokens | Turn Δ | Duration Δ | Token Δ |")
    lines.append("|------|:----:|:---------:|:------------:|:----------:|:------:|:----------:|:-------:|")
    for rec in records:
        val = rec.get("validation")
        eff = rec.get("efficiency", {})
        if val:
            td = eff.get("turn_delta")
            td_str = f"{td:+.1f}" if td is not None else "—"
            dd = eff.get("duration_delta_pct")
            dd_str = f"{dd:+.0f}%" if dd is not None else "—"
            tkd = eff.get("token_delta_pct")
            tkd_str = f"{tkd:+.0f}%" if tkd is not None else "—"
            lines.append(
                f"| {rec['task']} "
                f"| {_fmt_phase(val)} "
                f"| {_fmt_float(val.get('avg_turns'))} "
                f"| {_fmt_float(val.get('avg_duration'))}s "
                f"| {_fmt_tokens(val.get('avg_tokens'))} "
                f"| {td_str} | {dd_str} | {tkd_str} |"
            )
    lines.append("")

    # -----------------------------------------------------------------------
    # Evolved vs Curated
    # -----------------------------------------------------------------------
    lines.append("## A vs B vs C vs D Comparison")
    lines.append("")
    lines.append("Conditions: A=No Skill, B=Curated (human), C=Evolved (full pipeline), D=Evolved (no-trace ablation)")
    lines.append("")
    lines.append("| Task | A: No Skill | D: No-Trace | C: Evolved | C: Mean Reward | B: Curated | C vs B |")
    lines.append("|------|:-----------:|:-----------:|:----------:|:--------------:|:----------:|:------:|")
    for rec in records:
        eff = rec.get("efficiency", {})
        notrace = rec.get("notrace_validation") or {}
        notrace_str = _fmt_float(notrace.get("pass_rate"), 2) if notrace.get("pass_rate") is not None else "—"
        mean_r = eff.get("evolved_mean_reward")
        mean_r_str = _fmt_float(mean_r, 2) if mean_r is not None else "—"
        lines.append(
            f"| {rec['task']} "
            f"| {_fmt_float(rec.get('o46_no'), 1)} "
            f"| {notrace_str} "
            f"| {_fmt_float(eff.get('evolved_pass_rate'), 2)} "
            f"| {mean_r_str} "
            f"| {_fmt_float(eff.get('curated_pass_rate'), 1)} "
            f"| {eff.get('evolved_vs_curated', '—')} |"
        )
    lines.append("")

    # -----------------------------------------------------------------------
    # Oracle Peek Audit (anti-leak post-hoc check)
    # -----------------------------------------------------------------------
    lines.append("## Oracle Peek Audit")
    lines.append("")
    lines.append(
        "Did the skill-creator agent read `train-context/solution/solve.sh`, "
        "`train-context/tests/test_outputs.py`, or any curated training skill "
        "during Phase 3? Tasks where C beats A *without* an oracle read are "
        "evidence that the lift is from genuine trace-distillation, not "
        "training-oracle leakage."
    )
    lines.append("")
    lines.append("| Task | A→C lift | solve.sh | test_outputs.py | train skill | Any peek | Verdict |")
    lines.append("|------|:--------:|:--------:|:---------------:|:-----------:|:--------:|---------|")

    # Versions where train-oracle reads are expected by design (not a leak signal).
    # Empty in this release; populate if you add a baseline that reads
    # train-context/ by construction.
    EXPECTED_TRAIN_ORACLE_VERSIONS: set[str] = set()

    n_clean_lift = 0      # C > A and no oracle read
    n_lift_with_peek = 0  # C > A and oracle was read
    n_no_lift = 0
    n_no_audit = 0
    n_expected_oracle = 0  # Baseline versions where train-oracle reads are expected

    for rec in records:
        audit = rec.get("oracle_audit") or {}
        eff = rec.get("efficiency", {})
        evolved = eff.get("evolved_pass_rate")
        a_pass = rec.get("o46_no")
        version = rec.get("version") or ""

        if evolved is None or a_pass is None:
            verdict = "no_data"
            n_no_audit += 1
            lift_str = "—"
        else:
            lift = evolved - a_pass
            lift_str = f"{lift:+.2f}"
            if audit.get("any_oracle_read") and version in EXPECTED_TRAIN_ORACLE_VERSIONS:
                verdict = "expected_train_oracle_read"
                n_expected_oracle += 1
            elif lift <= 0.0:
                verdict = "no_lift"
                n_no_lift += 1
            elif audit.get("any_oracle_read"):
                verdict = "lift_with_peek"
                n_lift_with_peek += 1
            else:
                verdict = "**clean_lift**"
                n_clean_lift += 1

        def _mk(b: bool | None) -> str:
            if not audit.get("agent_log_present"):
                return "—"
            return "✅" if b else "·"

        lines.append(
            f"| {rec['task']} "
            f"| {lift_str} "
            f"| {_mk(audit.get('read_solve_sh'))} "
            f"| {_mk(audit.get('read_test_outputs'))} "
            f"| {_mk(audit.get('read_train_skill'))} "
            f"| {'⚠️' if audit.get('any_oracle_read') else '·'} "
            f"| {verdict} |"
        )
    lines.append("")
    lines.append(
        f"**Aggregate:** {n_clean_lift} clean lifts (C>A, no oracle peek) · "
        f"{n_lift_with_peek} lifts with oracle peek · "
        f"{n_no_lift} no lift · {n_no_audit} no audit data · "
        f"{n_expected_oracle} expected train oracle reads (baseline versions)"
    )
    lines.append("")
    lines.append(
        "_Clean lifts are the strongest evidence that trace-distillation "
        "alone (no oracle peek) is producing the gains. Lifts with peek "
        "are still valid C results but cannot be cleanly attributed to "
        "trace-distillation vs. oracle reading._"
    )
    lines.append("")

    return "\n".join(lines)


def generate_detail_report(
    records: list[dict],
    analyses: dict[str, dict],
    patterns_body: str,
) -> str:
    """Generate per-task detailed analysis + emerging patterns as a separate document."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    lines.append(f"<!-- AUTO-GENERATED by scripts/aggregate_results.py on {now} — DO NOT EDIT MANUALLY -->")
    lines.append("")
    lines.append("# Per-Task Detailed Analysis")
    lines.append("")

    for rec in records:
        task = rec["task"]
        icon = _OUTCOME_ICON.get(rec["outcome"], rec["outcome"])
        lines.append(f"## {task} {icon}")
        lines.append("")

        # Metrics header
        exp = rec.get("exploration")
        val = rec.get("validation")
        baseline_str = (
            f"O46 no-skill={rec.get('o46_no')}, O46 curated={rec.get('o46_with')}"
            if rec.get("o46_no") is not None
            else "no baseline data"
        )
        cost_str = f"${rec.get('total_cost_usd'):.2f}" if rec.get("total_cost_usd") else "\u2014"

        lines.append(f"**Baseline**: {baseline_str}")
        lines.append(f"**Cost**: {cost_str}")
        lines.append(f"**Skill**: {rec.get('skill') or '\u2014'} | **Category**: {rec.get('category') or '\u2014'}")
        lines.append("")

        # Trial table
        lines.append("| Phase | Pass | Avg Turns | Avg Tokens |")
        lines.append("|-------|:----:|:---------:|:----------:|")
        if exp:
            lines.append(
                f"| Exploration | {_fmt_phase(exp)} "
                f"| {_fmt_float(exp.get('avg_turns'))} "
                f"| {_fmt_tokens(exp.get('avg_tokens'))} |"
            )
        if val:
            lines.append(
                f"| Validation | {_fmt_phase(val)} "
                f"| {_fmt_float(val.get('avg_turns'))} "
                f"| {_fmt_tokens(val.get('avg_tokens'))} |"
            )
        lines.append("")

        # Injected analysis body
        analysis = analyses.get(task, {})
        body = analysis.get("body", "").strip() if analysis else ""
        if body:
            lines.append(body)
        else:
            lines.append("_(no analysis yet)_")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Emerging Patterns (appended at the end)
    lines.append("# Emerging Patterns")
    lines.append("")
    if patterns_body and patterns_body.strip():
        lines.append(patterns_body.strip())
    else:
        lines.append("_(no patterns analysis yet)_")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Task 6: CLI Interface
# ---------------------------------------------------------------------------

def _sort_records(records: list[dict]) -> list[dict]:
    """Sort records: success first, then partial, fail, incomplete; alpha within group."""
    order = {"success": 0, "partial": 1, "fail": 2, "incomplete": 3}
    return sorted(records, key=lambda r: (order.get(r.get("outcome", "incomplete"), 99), r.get("task", "")))


def _run(args: argparse.Namespace) -> None:
    """Main orchestration function."""
    # Load baselines
    baselines = parse_baselines() if CATEGORIZATION_FILE.exists() else {}

    # Load analyses
    patterns_body = ""
    if ANALYSIS_DIR.is_dir():
        analyses = load_all_analyses(ANALYSIS_DIR)
        patterns_file = ANALYSIS_DIR / "_patterns.md"
        if patterns_file.exists():
            _, patterns_body = parse_analysis_file(patterns_file.read_text(encoding="utf-8"))
    else:
        analyses = {}

    # Discover tasks
    task_filter = getattr(args, "task", None)
    version = getattr(args, "version", "evolver")
    tasks = discover_tasks(EVOLVED_SKILLS_DIR, version=version)
    if task_filter:
        tasks = {k: v for k, v in tasks.items() if k == task_filter}

    # Build records (full pipeline runs, condition C)
    records = []
    for slug, ts_dir in tasks.items():
        try:
            task_data = load_task_data(ts_dir)
        except Exception as e:
            print(f"WARNING: failed to load {slug}: {e}", file=sys.stderr)
            continue
        baseline = baselines.get(slug)
        analysis_meta = analyses.get(slug, {}).get("meta") if analyses.get(slug) else None
        rec = build_record(slug, task_data, baseline, analysis_meta)
        records.append(rec)

    # Attach no-trace ablation data (condition D) — separate from full runs
    notrace_runs = discover_notrace_runs(EVOLVED_SKILLS_DIR)
    if task_filter:
        notrace_runs = {k: v for k, v in notrace_runs.items() if k == task_filter}
    rec_by_slug = {r["task"]: r for r in records}

    for slug, ts_dir in notrace_runs.items():
        val_path = ts_dir / "task" / "validation-results.json"
        notrace_data = {"pass": None, "attempts": None, "pass_rate": None}
        try:
            val_json = json.loads(val_path.read_text(encoding="utf-8"))
            n_pass = val_json.get("n_passed", 0)
            n_att = val_json.get("n_attempts", 0) or len(val_json.get("trials", []))
            notrace_data = {
                "pass": n_pass,
                "attempts": n_att,
                "pass_rate": round(n_pass / n_att, 3) if n_att else None,
            }
        except Exception as e:
            print(f"WARNING: failed to load no-trace validation for {slug}: {e}", file=sys.stderr)

        if slug in rec_by_slug:
            rec_by_slug[slug]["notrace_validation"] = notrace_data
        else:
            # Task has only a no-trace run, no full run — create a minimal stub record
            stub = {
                "task": slug,
                "outcome": "incomplete",
                "category": baselines.get(slug, {}).get("category"),
                "domain": baselines.get(slug, {}).get("domain"),
                "o46_no": baselines.get(slug, {}).get("o46_no"),
                "exploration": None,
                "validation": None,
                "efficiency": {},
                "notrace_validation": notrace_data,
            }
            records.append(stub)
            rec_by_slug[slug] = stub

    # Inject A-category baseline-pass tasks (O46 already ≥0.8 without skills).
    # These are not run through the C pipeline because the agent already solves
    # them; count them as pass so the report reflects full coverage.
    existing = {r["task"] for r in records}
    for slug, b in baselines.items():
        if slug in existing:
            continue
        if task_filter and slug != task_filter:
            continue
        if (b.get("o46_no") or 0) < 0.8:
            continue
        records.append({
            "task": slug,
            "domain": b.get("domain"),
            "category": "A",
            "outcome": "success",
            "skill": None,
            "notes": "baseline-pass (A): O46 ≥0.8 without skills, C pipeline not run",
            "timestamp": None,
            "total_cost_usd": None,
            "o46_no": b.get("o46_no"),
            "s45_no": b.get("s45_no"),
            "o46_with": b.get("o46_with"),
            "s45_with": b.get("s45_with"),
            "exploration": None,
            "validation": None,
            "efficiency": {
                "evolved_pass_rate": b.get("o46_no"),
                "curated_pass_rate": b.get("o46_with"),
                "evolved_vs_curated": "baseline_pass",
            },
            "oracle_audit": {"agent_log_present": False, "any_oracle_read": False},
        })

    # Inject remaining baseline tasks (D-hopeless / unrun / non-runnable) as C=0.
    # Per operator decision: anything we couldn't run counts as 0 in the C column.
    existing = {r["task"] for r in records}
    for slug, b in baselines.items():
        if slug in existing:
            continue
        if task_filter and slug != task_filter:
            continue
        records.append({
            "task": slug,
            "domain": b.get("domain"),
            "category": None,
            "outcome": "not_run",
            "skill": None,
            "notes": "not yet run — placeholder C=0 for aggregate stats only; not a verdict",
            "timestamp": None,
            "total_cost_usd": None,
            "o46_no": b.get("o46_no"),
            "s45_no": b.get("s45_no"),
            "o46_with": b.get("o46_with"),
            "s45_with": b.get("s45_with"),
            "exploration": None,
            "validation": None,
            "efficiency": {
                "evolved_pass_rate": 0.0,
                "curated_pass_rate": b.get("o46_with"),
                "evolved_vs_curated": (
                    "both_fail" if (b.get("o46_with") or 0) <= 0.2
                    else "evolved_lt_curated"
                ),
            },
            "oracle_audit": {"agent_log_present": False, "any_oracle_read": False},
        })

    # Sort
    records = _sort_records(records)

    if getattr(args, "summary", False):
        # Print summary table to stdout
        print(f"{'#':<3} {'Task':<40} {'Cat':<5} {'Domain':<10} {'Exp':>6} {'Val':>6} {'Outcome'}")
        print("-" * 85)
        for i, rec in enumerate(records, 1):
            print(
                f"{i:<3} {rec['task']:<40} {rec.get('category') or '—':<5} "
                f"{rec.get('domain') or '—':<10} "
                f"{_fmt_phase(rec.get('exploration')):>6} "
                f"{_fmt_phase(rec.get('validation')):>6}  "
                f"{rec['outcome']}"
            )
        print(f"\nTotal: {len(records)} tasks")
        return

    # Full mode: write output files
    JSONL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with JSONL_OUTPUT.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, default=str) + "\n")
    print(f"Wrote {len(records)} records to {JSONL_OUTPUT}", file=sys.stderr)

    report = generate_report(records)
    REPORT_OUTPUT.write_text(report, encoding="utf-8")
    print(f"Wrote report to {REPORT_OUTPUT}", file=sys.stderr)

    detail = generate_detail_report(records, analyses, patterns_body)
    DETAIL_OUTPUT.write_text(detail, encoding="utf-8")
    print(f"Wrote detail report to {DETAIL_OUTPUT}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate self-evolving skills results into JSONL + markdown report."
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print compact summary table to stdout; do not write files.",
    )
    parser.add_argument(
        "--task",
        metavar="TASK",
        default=None,
        help="Only process this task slug (still regenerates full output).",
    )
    parser.add_argument(
        "--version",
        default="evolver",
        choices=sorted(KNOWN_VERSIONS),
        help="Which pipeline version's runs to aggregate (default: evolver).",
    )
    args = parser.parse_args()
    _run(args)


if __name__ == "__main__":
    main()
