"""Token/cost statistics and result aggregation for skill-creator runs."""

import datetime
import json
from pathlib import Path

from .config import estimate_cost_usd


def extract_metrics_from_jsonl(input_path: str) -> dict:
    """
    Extract token usage and turn-count metrics from a Harbor .jsonl log.

    Returns
    -------
    dict with keys:
        input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,
        total_tokens, n_turns, duration_seconds
    """
    input_tokens = 0
    output_tokens = 0
    n_turns = 0
    timestamps: list[float] = []

    # Track which message IDs we've seen to avoid double-counting streaming chunks
    seen_message_ids: set[str] = set()

    with open(input_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)

            # Collect timestamps for duration
            ts_str = event.get("timestamp")
            if ts_str:
                try:
                    # Remove trailing Z and parse as UTC
                    ts_str_clean = ts_str.rstrip("Z").split(".")[0]
                    dt = datetime.datetime.fromisoformat(ts_str_clean)
                    timestamps.append(dt.timestamp())
                except (ValueError, AttributeError):
                    pass

            ev_type = event.get("type", "")
            if ev_type != "assistant":
                continue

            message = event.get("message", {})
            msg_id = message.get("id", "")
            usage = message.get("usage")

            if usage is None:
                continue

            # Only count usage once per message ID (streaming sends multiple chunks)
            # Use the last chunk for each message ID (highest output_tokens)
            # Strategy: accumulate by tracking last-seen usage per message id
            # We handle this by scanning all events and keeping a dict
            # For simplicity here, count each event but deduplicate by message_id below
            # We'll use a two-pass approach to handle duplicates properly.

            # Count assistant turns (unique messages)
            if msg_id:
                if msg_id not in seen_message_ids:
                    seen_message_ids.add(msg_id)
                    n_turns += 1
                    # Only count tokens for the last chunk (highest output_tokens)
                    # We do a second pass below for accuracy
            else:
                # No message ID — count each event
                n_turns += 1

    # Second pass: collect per-message final usage (last chunk wins)
    per_message_usage: dict[str, dict] = {}
    no_id_usages: list[dict] = []

    with open(input_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get("type") != "assistant":
                continue
            message = event.get("message", {})
            msg_id = message.get("id", "")
            usage = message.get("usage")
            if usage is None:
                continue
            if msg_id:
                # Last entry wins (streaming sends incremental chunks)
                per_message_usage[msg_id] = usage
            else:
                no_id_usages.append(usage)

    all_usages = list(per_message_usage.values()) + no_id_usages
    n_turns = len(per_message_usage) + len(no_id_usages)

    cache_read_tokens = 0
    cache_creation_tokens = 0

    for usage in all_usages:
        it = usage.get("input_tokens", 0) or 0
        cr = usage.get("cache_read_input_tokens", 0) or 0
        cc = usage.get("cache_creation_input_tokens", 0) or 0
        ot = usage.get("output_tokens", 0) or 0
        input_tokens += it
        output_tokens += ot
        cache_read_tokens += cr
        cache_creation_tokens += cc

    total_tokens = input_tokens + output_tokens + cache_read_tokens + cache_creation_tokens

    duration_seconds: float = 0.0
    if len(timestamps) >= 2:
        duration_seconds = max(timestamps) - min(timestamps)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "total_tokens": total_tokens,
        "n_turns": n_turns,
        "duration_seconds": duration_seconds,
    }


def build_result_json(
    workspace: Path,
    task_name: str,
    model: str,
    agent_cost_usd_sdk: float | None,
    agent_turns: int | None,
    agent_input_tokens: int = 0,
    agent_output_tokens: int = 0,
    agent_cache_read_tokens: int = 0,
    agent_cache_creation_tokens: int = 0,
    harbor_model: str | None = None,
    pipeline_version: str | None = None,
) -> None:
    """Aggregate phase results into a single structured result.json."""
    # Harbor trials use the model passed to run_and_wait.py (usually sonnet)
    # The agent itself uses the orchestrator model (usually opus)
    h_model = harbor_model or model

    task_dir = workspace / "task"

    # Discover exploration result files (k-suffixed or legacy naming)
    phase_files = {}
    for k in range(10):
        kpath = task_dir / f"exploration-results-k{k}.json"
        if kpath.exists():
            phase_files[f"exploration_k{k}"] = kpath
    # Fallback to old naming (pre-unified-loop runs)
    if not phase_files:
        old_exp = task_dir / "exploration-results.json"
        if old_exp.exists():
            phase_files["exploration"] = old_exp
    # Legacy refine results (backward compat with old evolver runs)
    refine_path = task_dir / "refine-results.json"
    if refine_path.exists():
        phase_files["refine"] = refine_path
    # Validation
    val_path = task_dir / "validation-results.json"
    if val_path.exists():
        phase_files["validation"] = val_path

    phases = {}
    total_harbor_cost = 0.0
    for phase_key, path in phase_files.items():
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        trials = data.get("trials", [])

        inp_tokens = [t.get("input_tokens", 0) for t in trials]
        out_tokens = [t.get("output_tokens", 0) for t in trials]
        cr_tokens = [t.get("cache_read_tokens", 0) for t in trials]
        cc_tokens = [t.get("cache_creation_tokens", 0) for t in trials]
        tot_tokens = [t.get("total_tokens", 0) for t in trials]
        turns = [t.get("n_turns", 0) for t in trials]
        durations = [t.get("duration_seconds", 0.0) for t in trials]
        n = len(trials) or 1

        # Estimate cost for this phase
        phase_cost = None
        if sum(inp_tokens) > 0 or sum(out_tokens) > 0 or sum(cr_tokens) > 0 or sum(cc_tokens) > 0:
            phase_cost = estimate_cost_usd(
                sum(inp_tokens), sum(out_tokens), h_model,
                cache_read_tokens=sum(cr_tokens),
                cache_creation_tokens=sum(cc_tokens),
            )
        elif sum(tot_tokens) > 0:
            # Fallback: assume 80% input / 20% output ratio for old data
            est_inp = int(sum(tot_tokens) * 0.8)
            est_out = sum(tot_tokens) - est_inp
            phase_cost = estimate_cost_usd(est_inp, est_out, h_model)

        if phase_cost is not None:
            total_harbor_cost += phase_cost

        phases[phase_key] = {
            "n_passed": data.get("n_passed", 0),
            "n_failed": data.get("n_failed", 0),
            "n_attempts": data.get("n_attempts", 0),
            "pass_rate": data.get("n_passed", 0) / max(data.get("n_attempts", 1), 1),
            "total_input_tokens": sum(inp_tokens),
            "total_output_tokens": sum(out_tokens),
            "total_tokens": sum(tot_tokens),
            "avg_input_tokens": sum(inp_tokens) // n,
            "avg_output_tokens": sum(out_tokens) // n,
            "avg_total_tokens": sum(tot_tokens) // n,
            "avg_turns": round(sum(turns) / n, 1),
            "avg_duration_seconds": round(sum(durations) / n, 1),
            "estimated_cost_usd": phase_cost,
            "trials": trials,
        }

    # Aggregate harbor token totals across all phases
    harbor_input = sum(p.get("total_input_tokens", 0) for p in phases.values())
    harbor_output = sum(p.get("total_output_tokens", 0) for p in phases.values())
    harbor_cache_read = sum(
        sum(t.get("cache_read_tokens", 0) for t in p.get("trials", []))
        for p in phases.values()
    )
    harbor_cache_creation = sum(
        sum(t.get("cache_creation_tokens", 0) for t in p.get("trials", []))
        for p in phases.values()
    )
    harbor_total = sum(p.get("total_tokens", 0) for p in phases.values())

    train_oracle_path = workspace / "train-oracle-result.json"
    train_oracle_reward = None
    if train_oracle_path.exists():
        try:
            train_oracle_reward = json.loads(train_oracle_path.read_text()).get("reward")
        except json.JSONDecodeError:
            pass

    iterations_run = None
    iters_marker = workspace / ".iterations_run"
    if iters_marker.exists():
        try:
            iterations_run = int(iters_marker.read_text().strip())
        except ValueError:
            pass

    result = {
        "task": task_name,
        "pipeline_version": pipeline_version,
        "timestamp": datetime.datetime.now().isoformat(),
        # --- Summary (key numbers at the top) ---
        "agent_cost_usd": agent_cost_usd_sdk,
        "agent_tokens": {
            "input": agent_input_tokens,
            "output": agent_output_tokens,
            "cache_read": agent_cache_read_tokens,
            "cache_creation": agent_cache_creation_tokens,
        },
        "harbor_cost_usd": round(total_harbor_cost, 4),
        "harbor_tokens": {
            "input": harbor_input,
            "output": harbor_output,
            "cache_read": harbor_cache_read,
            "cache_creation": harbor_cache_creation,
            "total": harbor_total,
        },
        # --- Details ---
        "model": model,
        "harbor_model": h_model,
        "agent_turns": agent_turns,
        "phases": phases,
        # --- Baseline fields (None unless set by baseline runners) ---
        "iterations_run": iterations_run,
        "train_oracle_reward": train_oracle_reward,
    }

    (workspace / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n[result.json] saved to {workspace / 'result.json'}")
