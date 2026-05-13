"""
SkillEvolver agent runner.

Creates a workspace, then launches a single Agent SDK session that runs the full
explore → analyze → update loop end-to-end. The agent calls
``skill-evolver/benchmarks/harbor/scripts/run_and_wait.py`` to drive Harbor
trials — it never touches Harbor directly.

Usage:
    python -m agent.run --task sales-pivot-analysis --train-split
    python -m agent.run --task sales-pivot-analysis --train-split --iterations 1
    python -m agent.run --task sales-pivot-analysis \
        --deploy-from evolved-skills/evolver/sales-pivot-analysis/<timestamp>/output/skills/<skill-name>
"""




import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import anyio
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    ToolUseBlock,
    TextBlock,
    HookMatcher,
)

from .config import (
    DEFAULT_MODEL,
    EVOLVER_DEFAULT_ITERATIONS,
    EVOLVER_MAX_BUDGET,
    EVOLVER_MAX_ITERATIONS,
    EVOLVER_MAX_TURNS,
    EVOLVER_N_EXPLORATION,
    EVOLVER_N_VALIDATION,
    EVOLVER_PASS_REWARD_MIN,
    EVOLVER_REWARD_SIGNAL_MODE,
    MAX_BUDGET,
    MAX_TURNS,
    TASKS_TRAIN_DIR,
    TASKS_EVOLVED_SKILLS_DIR,
)
from .prompts import (
    build_system_prompt_evolver,
    build_user_prompt_evolver,
)
from .results import build_result_json
from .workspace import create_agent_venv, load_task_context, ensure_task_variant, deploy_skills, setup_workspace
from .guards import configure_allowed_prefixes, check_path_access, check_bash_command


async def _path_guard_hook(input_data, tool_use_id, context):
    """PreToolUse hook — whitelist-only access control.

    Uses hooks instead of can_use_tool because the latter requires
    --permission-prompt-tool CLI support (not available in CLI 2.1.x).
    Hooks are processed by the CLI directly and work with all permission modes.
    """
    tool_name = input_data["tool_name"]
    tool_input = input_data.get("tool_input", {})

    # Block Agent tool — subagents bypass guards
    deny_reason = None
    if tool_name == "Agent":
        deny_reason = "Agent tool is not available. Work within your own session."
    elif tool_name in ("Read", "Write", "Edit"):
        path = tool_input.get("file_path", "")
        if path:
            deny_reason = check_path_access(path)
    elif tool_name in ("Grep", "Glob"):
        path = tool_input.get("path", "")
        if path:
            deny_reason = check_path_access(path)
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        deny_reason = check_bash_command(cmd)

    if deny_reason:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reason,
            },
        }

    # Allow — return permissionDecision explicitly
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        },
    }


async def run_skill_creator(
    task_name: str,
    instruction: str,
    dockerfile: str,
    workspace: Path,
    model: str = DEFAULT_MODEL,
    max_turns: int = MAX_TURNS,
    max_budget: float = MAX_BUDGET,
    version: str = "evolver",
    tmux_window: str = "skillsbench:1",
    use_train_split: bool = False,
    iterations: int = 2,
    seed_skill_dir: str | None = None,
    n_exploration: int | None = None,
    n_validation: int | None = None,
    max_iterations: int | None = None,
    reward_signal_mode: str | None = None,
    pass_reward_min: float | None = None,
) -> str:
    """Launch a single Agent SDK session to run the full SkillEvolver pipeline."""
    if version != "evolver":
        raise ValueError(f"Unknown version: {version}. Only 'evolver' is supported.")

    skill_creator_dir = str(workspace / "skill-evolver")
    system_prompt = build_system_prompt_evolver(skill_creator_dir)
    user_prompt = build_user_prompt_evolver(
        task_name=task_name,
        instruction=instruction,
        dockerfile=dockerfile,
        workspace_dir=str(workspace),
        model=model,
        n_exploration=n_exploration if n_exploration is not None else EVOLVER_N_EXPLORATION,
        n_validation=n_validation if n_validation is not None else EVOLVER_N_VALIDATION,
        max_iterations=max_iterations if max_iterations is not None else iterations,
        tmux_window=tmux_window,
        use_train_split=use_train_split,
        seed_skill_dir=seed_skill_dir,
        reward_signal_mode=reward_signal_mode if reward_signal_mode is not None else EVOLVER_REWARD_SIGNAL_MODE,
        pass_reward_min=pass_reward_min if pass_reward_min is not None else EVOLVER_PASS_REWARD_MIN,
    )

    # Create clean venv and inject into PATH so agent's Bash uses it
    venv_bin = create_agent_venv(workspace)
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{venv_bin}:{old_path}"

    reward_signal_old = os.environ.get("SKILLSBENCH_REWARD_SIGNAL_MODE")
    pass_reward_old = os.environ.get("SKILLSBENCH_PASS_REWARD_MIN")
    os.environ["SKILLSBENCH_REWARD_SIGNAL_MODE"] = (
        reward_signal_mode if reward_signal_mode is not None else EVOLVER_REWARD_SIGNAL_MODE
    )
    os.environ["SKILLSBENCH_PASS_REWARD_MIN"] = str(
        pass_reward_min if pass_reward_min is not None else EVOLVER_PASS_REWARD_MIN
    )

    # Configure anti-cheating path guard
    from .config import PROJECT_ROOT
    configure_allowed_prefixes(workspace, PROJECT_ROOT)

    print(f"Launching skill-creator agent...")
    print(f"  Workspace: {workspace}")
    print(f"  Agent venv: {venv_bin}")
    print(f"  Model: {model}")
    print(f"  Budget: ${max_budget:.2f}, Max turns: {max_turns}")

    # Claude Code CLI rejects bypass-permissions when running as root.
    # Keep our own path/tool hooks active, but fall back to acceptEdits
    # so root-based harness runs can still start.
    permission_mode = "bypassPermissions"
    if os.geteuid() == 0:
        permission_mode = "acceptEdits"

    log_path = workspace / "agent.log"
    log_file = open(log_path, "w", encoding="utf-8")
    print(f"  Log: {log_path}")

    def log(line: str):
        """Print to stdout and write to log file."""
        print(line)
        log_file.write(line + "\n")
        log_file.flush()

    result_text = ""
    agent_cost_usd = None
    agent_turns = None
    agent_input_tokens = 0
    agent_output_tokens = 0
    agent_cache_read_tokens = 0
    agent_cache_creation_tokens = 0

    pipeline_complete = False

    # Hooks require stdin to stay open for the control protocol. With a string
    # prompt, the SDK synchronously awaits wait_for_result_and_end_input() which
    # blocks until session end. With an async iterable, stream_input runs in a
    # background task so message iteration proceeds immediately. The sleep keeps
    # stdin open; it gets cancelled when the task group shuts down.
    async def _keep_stdin_open():
        yield {
            "type": "user",
            "message": {"role": "user", "content": user_prompt},
        }
        await anyio.sleep(7200)  # Cancelled when session ends

    try:
        async for message in query(
            prompt=_keep_stdin_open(),
            options=ClaudeAgentOptions(
                cwd=str(workspace),
                allowed_tools=[
                    "Read", "Write", "Edit", "Bash", "Glob", "Grep",
                    "WebSearch", "WebFetch",
                ],
                system_prompt=system_prompt,
                model=model,
                max_turns=max_turns,
                max_budget_usd=max_budget,
                permission_mode=permission_mode,
                hooks={
                    "PreToolUse": [
                        HookMatcher(
                            matcher="Read|Write|Edit|Bash|Glob|Grep|Agent",
                            hooks=[_path_guard_hook],
                        ),
                    ],
                },
            ),
        ):
            if isinstance(message, AssistantMessage):
                # Accumulate token usage
                if message.usage:
                    u = message.usage
                    agent_input_tokens += u.get("input_tokens", 0) or 0
                    agent_output_tokens += u.get("output_tokens", 0) or 0
                    agent_cache_read_tokens += u.get("cache_read_input_tokens", 0) or 0
                    agent_cache_creation_tokens += u.get("cache_creation_input_tokens", 0) or 0
                for block in message.content:
                    if isinstance(block, TextBlock):
                        # Show full text to terminal, write to log
                        text = block.text.strip()
                        if text:
                            log(f"\n{text}")
                        # Hard stop: detect pipeline completion signal
                        if "PIPELINE COMPLETE" in (block.text or ""):
                            pipeline_complete = True
                    elif isinstance(block, ToolUseBlock):
                        name = block.name
                        inp = block.input or {}
                        # Clean, readable tool call display
                        if name == "Bash":
                            cmd = inp.get("command", "")
                            desc = inp.get("description", "")
                            log(f"\n> [{name}] {desc or cmd[:120]}")
                        elif name == "Read":
                            log(f"\n> [{name}] {inp.get('file_path', '')}")
                        elif name in ("Write", "Edit"):
                            log(f"\n> [{name}] {inp.get('file_path', '')}")
                        else:
                            log(f"\n> [{name}]")
                        # Full tool input to log file only
                        log_file.write(f"[TOOL] {name}: {json.dumps(inp, ensure_ascii=False)}\n")
                        log_file.flush()
                # Hard stop after processing all blocks in this message
                if pipeline_complete:
                    log(f"\n{'='*60}")
                    log(f"PIPELINE COMPLETE detected — terminating agent session.")
                    log(f"{'='*60}")
                    break
            elif isinstance(message, ResultMessage):
                result_text = message.result or ""
                agent_cost_usd = message.total_cost_usd
                agent_turns = message.num_turns
                cost = f"${agent_cost_usd:.2f}" if agent_cost_usd else "N/A"
                log(f"\n{'='*60}")
                log(f"Agent completed. Turns: {agent_turns}, Cost: {cost}, Error: {message.is_error}")
                log(f"{'='*60}")
                log_file.write(f"[RESULT] {result_text}\n")
                log_file.flush()
            elif isinstance(message, SystemMessage) and message.subtype == "init":
                session_id = message.data.get("session_id")
                log(f"Session: {session_id}")
    except (RuntimeError, GeneratorExit) as e:
        # Expected when breaking the async generator — anyio cancel scope cleanup error
        if "cancel scope" in str(e) or pipeline_complete:
            pass
        else:
            raise
    log_file.close()

    # Restore original PATH / reward-signal env
    os.environ["PATH"] = old_path
    if reward_signal_old is None:
        os.environ.pop("SKILLSBENCH_REWARD_SIGNAL_MODE", None)
    else:
        os.environ["SKILLSBENCH_REWARD_SIGNAL_MODE"] = reward_signal_old
    if pass_reward_old is None:
        os.environ.pop("SKILLSBENCH_PASS_REWARD_MIN", None)
    else:
        os.environ["SKILLSBENCH_PASS_REWARD_MIN"] = pass_reward_old

    # Save run metadata
    metadata = {
        "task": task_name,
        "model": model,
        "max_turns": max_turns,
        "max_budget_usd": max_budget,
        "timestamp": datetime.now().isoformat(),
        "agent_result_summary": result_text[:1000] if result_text else "",
    }
    (workspace / "metadata.json").write_text(json.dumps(metadata, indent=2))

    # Build structured result.json from phase results
    build_result_json(
        workspace,
        task_name=task_name,
        model=model,
        agent_cost_usd_sdk=agent_cost_usd,
        agent_turns=agent_turns,
        agent_input_tokens=agent_input_tokens,
        agent_output_tokens=agent_output_tokens,
        agent_cache_read_tokens=agent_cache_read_tokens,
        agent_cache_creation_tokens=agent_cache_creation_tokens,
        pipeline_version=version,
    )

    return result_text


def print_summary(workspace: Path, task_name: str) -> None:
    """Print pipeline results summary from JSON files.

    No LLM needed — just read the JSONs and format a table.
    """
    task_dir = workspace / "task"

    def _load_phase(name: str) -> dict | None:
        path = task_dir / f"{name}-results.json"
        if path.exists():
            return json.loads(path.read_text())
        return None

    # Load all exploration iterations (k-suffixed naming)
    exploration_phases = []
    for k in range(10):
        kpath = task_dir / f"exploration-k{k}-results.json"
        if kpath.exists():
            exploration_phases.append((f"Explore k={k}", json.loads(kpath.read_text())))
    # Fallback to old naming
    if not exploration_phases:
        old = _load_phase("exploration")
        if old:
            exploration_phases.append(("Exploration", old))
    # Legacy refine (backward compat)
    refine = _load_phase("refine")
    if refine:
        exploration_phases.append(("Refine (legacy)", refine))

    validation = _load_phase("validation")

    print(f"\n{'='*60}")
    print(f"Pipeline Summary: {task_name}")
    print(f"{'='*60}")
    print(f"{'Phase':<20} {'Pass Rate':<15} {'Avg Tokens':<15} {'Avg Turns':<12} {'Avg Duration':<12}")
    print(f"{'-'*20} {'-'*15} {'-'*15} {'-'*12} {'-'*12}")

    for phase_name, data in exploration_phases:
        n_passed = data.get("n_passed", 0)
        n_attempts = data.get("n_attempts", 0)
        trials = data.get("trials", [])
        n = len(trials) or 1
        avg_tokens = sum(t.get("total_tokens", 0) for t in trials) // n
        avg_turns = sum(t.get("n_turns", 0) for t in trials) / n
        avg_dur = sum(t.get("duration_seconds", 0) for t in trials) / n
        pct = f"{n_passed}/{n_attempts} ({100*n_passed//max(n_attempts,1)}%)"
        tok_str = f"{avg_tokens//1000}k" if avg_tokens >= 1000 else str(avg_tokens)
        print(f"{phase_name:<20} {pct:<15} {tok_str:<15} {avg_turns:<12.1f} {avg_dur:<12.0f}s")

    if validation:
        n_passed = validation.get("n_passed", 0)
        n_attempts = validation.get("n_attempts", 0)
        trials = validation.get("trials", [])
        n = len(trials) or 1
        avg_tokens = sum(t.get("total_tokens", 0) for t in trials) // n
        avg_turns = sum(t.get("n_turns", 0) for t in trials) / n
        avg_dur = sum(t.get("duration_seconds", 0) for t in trials) / n
        pct = f"{n_passed}/{n_attempts} ({100*n_passed//max(n_attempts,1)}%)"
        tok_str = f"{avg_tokens//1000}k" if avg_tokens >= 1000 else str(avg_tokens)
        print(f"{'Validation':<20} {pct:<15} {tok_str:<15} {avg_turns:<12.1f} {avg_dur:<12.0f}s")
    else:
        print(f"{'Validation':<20} {'N/A':<15}")

    print(f"{'='*60}")


async def main():
    os.environ.pop("CLAUDECODE", None)

    # Suppress asyncio "Task exception was never retrieved" from generator cleanup
    import asyncio
    _default_handler = asyncio.get_event_loop().get_exception_handler()
    def _suppress_cancel_scope(loop, context):
        msg = str(context.get("exception", ""))
        if "cancel scope" in msg:
            return  # Expected: breaking async generator triggers anyio cleanup
        if _default_handler:
            _default_handler(loop, context)
        else:
            loop.default_exception_handler(context)
    asyncio.get_event_loop().set_exception_handler(_suppress_cancel_scope)

    parser = argparse.ArgumentParser(description="Run trace-distillation skill-creator pipeline")
    parser.add_argument("--task", required=True, help="Task name (e.g., sales-pivot-analysis)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model to use")
    parser.add_argument("--max-budget", type=float, default=MAX_BUDGET, help="Max budget in USD")
    parser.add_argument("--max-turns", type=int, default=MAX_TURNS, help="Max turns for the agent")
    parser.add_argument("--skip-deploy", action="store_true", help="Skip deploying skills after completion")
    parser.add_argument(
        "--deploy-from", type=str, default=None,
        help="Skip generation; deploy skills from this path",
    )
    parser.add_argument(
        "--seed-skill-dir", type=str, default=None,
        help="Bootstrap the run with a previously evolved skill directory containing SKILL.md",
    )
    parser.add_argument(
        "--version",
        choices=["evolver"],
        default="evolver",
        help="Pipeline version (single supported pipeline: 'evolver').",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help=f"Number of loop iterations (default: {EVOLVER_DEFAULT_ITERATIONS}). N=1 is the no-refinement ablation.",
    )
    parser.add_argument("--tmux-window", default="skillsbench:1", help="Tmux target window for Harbor (default: skillsbench:1)")
    parser.add_argument(
        "--train-split",
        action="store_true",
        help="Use train/test split: explore on tasks-train/, validate on tasks/",
    )
    parser.add_argument(
        "--n-exploration",
        type=int,
        default=None,
        help="Override exploration trial count per iteration.",
    )
    parser.add_argument(
        "--n-validation",
        type=int,
        default=None,
        help="Override final validation trial count.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Override skill-evolution iteration count (alias for --iterations).",
    )
    parser.add_argument(
        "--reward-signal-mode",
        choices=["auto", "discrete", "continuous"],
        default=None,
        help="Reward interpretation mode: auto | discrete | continuous.",
    )
    parser.add_argument(
        "--pass-reward-min",
        type=float,
        default=None,
        help="Secondary pass threshold for binarized accounting (continuous reward).",
    )
    args = parser.parse_args()

    # Auto-bump budget/turns when user didn't override
    if args.max_budget == MAX_BUDGET:
        args.max_budget = EVOLVER_MAX_BUDGET
    if args.max_turns == MAX_TURNS:
        args.max_turns = EVOLVER_MAX_TURNS

    task_name = args.task
    evolved_task_dir = TASKS_EVOLVED_SKILLS_DIR / task_name

    # --- Deploy-only mode ---
    if args.deploy_from:
        skills_path = Path(args.deploy_from)
        if not skills_path.is_absolute():
            skills_path = Path.cwd() / skills_path
        if not skills_path.exists():
            print(f"ERROR: Skills path does not exist: {skills_path}")
            return
        ensure_task_variant(task_name, evolved_task_dir)
        deploy_skills(skills_path, evolved_task_dir)
        print(f"\nDeployed. Run Harbor:")
        print(f"  cd Benchmarks/skillsbench && uv run harbor run -p tasks-evolved-skills/{task_name} -a claude-code -m '{args.model}'")
        return

    # --- Full pipeline mode ---
    print(f"=== Skill Creator Agent ({args.version}) ===")
    print(f"Task: {task_name}")
    print(f"Model: {args.model}")

    context_root = TASKS_TRAIN_DIR if args.train_split else None
    instruction, dockerfile, data_files = load_task_context(task_name, tasks_root=context_root)
    print(f"Loaded instruction ({len(instruction)} chars), Dockerfile ({len(dockerfile)} chars), {len(data_files)} data file(s)")
    if data_files:
        for f in data_files:
            print(f"  Data: {f.name}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    seed_skill_dir = None
    if args.seed_skill_dir:
        seed_skill_dir = Path(args.seed_skill_dir)
        if not seed_skill_dir.is_absolute():
            seed_skill_dir = Path.cwd() / seed_skill_dir
        if not seed_skill_dir.exists():
            raise FileNotFoundError(f"--seed-skill-dir does not exist: {seed_skill_dir}")
        print(f"Seed skill: {seed_skill_dir}")

    workspace = setup_workspace(
        task_name,
        timestamp,
        instruction,
        dockerfile,
        data_files,
        version=args.version,
        seed_skill_dir=seed_skill_dir,
    )
    print(f"Workspace: {workspace}")

    # Agent 1 (Opus): Phase 0 → 1 → 2 → launch Phase 3 → PIPELINE COMPLETE → killed
    await run_skill_creator(
        task_name=task_name,
        instruction=instruction,
        dockerfile=dockerfile,
        workspace=workspace,
        model=args.model,
        max_turns=args.max_turns,
        max_budget=args.max_budget,
        version=args.version,
        tmux_window=args.tmux_window,
        use_train_split=args.train_split,
        iterations=args.iterations or EVOLVER_DEFAULT_ITERATIONS,
        seed_skill_dir=str(seed_skill_dir) if seed_skill_dir else None,
        n_exploration=args.n_exploration,
        n_validation=args.n_validation,
        max_iterations=args.max_iterations,
        reward_signal_mode=args.reward_signal_mode,
        pass_reward_min=args.pass_reward_min,
    )

    # Print summary from JSON files (no LLM needed)
    print_summary(workspace, task_name)

    # Deploy output skills if they exist
    output_skills = workspace / "output" / "skills"
    if not args.skip_deploy and output_skills.exists():
        # Find skill subdirectories in output/skills/
        skill_dirs = [d for d in output_skills.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]
        if skill_dirs:
            ensure_task_variant(task_name, evolved_task_dir)
            deploy_skills(output_skills, evolved_task_dir)
            print(f"\nRun Harbor validation:")
            print(f"  cd Benchmarks/skillsbench && uv run harbor run -p tasks-evolved-skills/{task_name} -a claude-code -m '{args.model}'")
        else:
            print(f"\nWARNING: No skills found in {output_skills}")
    elif not args.skip_deploy:
        print(f"\nWARNING: Output skills directory not found at {output_skills}")

    print(f"\n=== Complete ===")
    print(f"Workspace: {workspace}")


if __name__ == "__main__":
    anyio.run(main)
