"""Prompts for the skill-evolver agent."""

from .config import (
    EVOLVER_DEFAULT_ITERATIONS,
    EVOLVER_MAX_ITERATIONS,
    EVOLVER_N_EXPLORATION,
    EVOLVER_N_VALIDATION,
    PROJECT_ROOT,
)


def build_system_prompt_evolver(skill_creator_dir: str) -> str:
    """System prompt for the looped SkillEvolver pipeline."""
    return f"""You are SkillEvolver. Your job is to create high-quality, reusable
agent skills through a repeated three-phase loop:

1. exploration
2. analyze traces
3. update skill

Follow the full pipeline in: {skill_creator_dir}/SKILL.md

CRITICAL CONSTRAINTS:
- You may ONLY read and write files within your workspace directory. Do not access any files outside it.
- File access is enforced — attempts to read files outside your workspace will be blocked.
- Use the benchmark-specific runner script provided in your user prompt — never call the benchmark harness directly.
- Every iteration must run a fresh exploration. Do NOT skip exploration and do NOT replay the exact same skill unchanged across all trials.
- There is no special first-skill-creation phase and no separate refine phase in this method.
- Final skills must be reusable knowledge artifacts, not task-local implementation notes.
- Final skills should include atomic operations, failure lessons, success contrasts, and conditional decision rules.
- Final skills must avoid embedding one task's concrete implementation as the skill itself.
- After final validation, STOP IMMEDIATELY. Output exactly "PIPELINE COMPLETE" and end your session. Do NOT continue exploring, debugging, or running more trials."""


def build_user_prompt_evolver(
    task_name: str,
    instruction: str,
    dockerfile: str,
    workspace_dir: str,
    model: str,
    n_exploration: int = EVOLVER_N_EXPLORATION,
    n_validation: int = EVOLVER_N_VALIDATION,
    max_iterations: int = EVOLVER_MAX_ITERATIONS,
    tmux_window: str = "harbor:0",
    use_train_split: bool = True,
    seed_skill_dir: str | None = None,
    reward_signal_mode: str = "auto",
    pass_reward_min: float = 0.0,
) -> str:
    """User prompt for SkillEvolver (looped exploration/analyze/update)."""
    project_root = str(PROJECT_ROOT)
    script = f"{project_root}/skill-evolver/benchmarks/harbor/scripts/run_and_wait.py"
    tmux_flag = f" --tmux-window {tmux_window}"
    tasks_dir_flag = " --tasks-dir tasks-train" if use_train_split else ""
    is_kernelbench = task_name.startswith("kb-")
    benchmark_name = "KernelBench" if is_kernelbench else "SkillsBench"
    fixed_skill_name = "kernel-optim" if is_kernelbench else None
    skill_name_ref = fixed_skill_name or "<skill-name>"

    reward_mode_section = ""
    if reward_signal_mode == "continuous":
        reward_mode_section = f"""
### Reward Signal Mode

This run uses **continuous reward mode**.

- Treat `raw_reward` and `mean_reward` as the primary optimization signals.
- Ignore pass rate for skill selection except as a weak secondary sanity check.
- After each exploration run, rank trials by `raw_reward` and analyze the highest-reward, middle, and lowest-reward trajectories.
- Use the binarized `reward` field only for coarse correctness context.
- Secondary binarization threshold (for summaries only): `raw_reward > {pass_reward_min}`.
"""
    elif reward_signal_mode == "discrete":
        reward_mode_section = f"""
### Reward Signal Mode

This run uses **discrete reward mode**.

- Treat thresholded pass/fail as the primary optimization signal.
- Use `raw_reward` as a tie-breaker inside the passing and failing sets.
- The binarization threshold is: `raw_reward > {pass_reward_min}`.
"""
    else:
        reward_mode_section = f"""
### Reward Signal Mode

This run uses **auto reward mode**.

- Read `task/exploration-results.json` after each run and check `signal_mode`.
- If `signal_mode = "continuous"`, optimize for `raw_reward` / `mean_reward` and treat pass rate as secondary.
- If `signal_mode = "discrete"`, use thresholded pass/fail as the primary signal and `raw_reward` as a tie-breaker.
- The secondary binarization threshold is: `raw_reward > {pass_reward_min}`.
"""

    train_split_section = ""
    if use_train_split:
        train_split_section = f"""

### Train/Test Split — CRITICAL: Your Skill Will Be Tested on DIFFERENT Files

- Every looped exploration runs on training data (`tasks-train/{task_name}`) — file names, content, and values may be DIFFERENT from the validation data
- Final validation runs on the original task (`tasks/{task_name}`) — DIFFERENT file names, DIFFERENT content. Your skill is graded here.

### Training-Task Ground Truth (read only when traces leave real uncertainty)

After an exploration run, the training task's labels may be copied into your workspace at `{workspace_dir}/task/train-context/`. This includes:

- `train-context/tests/test_outputs.py` — the training task's exact assertions
- `train-context/solution/solve.sh` — the training oracle
- `train-context/instruction.md` — the training instruction
- `train-context/environment/` — training data files

Use these only to resolve concrete uncertainty that traces alone cannot settle. Validation still runs on different data and filenames, so whatever you learn must be written as transferable guidance, not memorized task-specific steps.

### Mandatory Generalization Rules

1. NEVER hardcode training filenames, exact values, or task-instance-specific constants into the skill.
2. Teach the runtime agent to discover its own inputs from `instruction.md` and the working directory.
3. Bundled scripts must accept paths and parameters as arguments.
4. Before each skill update, check whether the draft would still work if all training filenames and values were renamed."""

    bootstrap_section = ""
    if seed_skill_dir:
        bootstrap_section = f"""

### Cross-Task Bootstrap Skill

This run is bootstrapped from a previously evolved skill:

- source path: `{seed_skill_dir}`
- copied into this workspace under: `{workspace_dir}/bootstrap/skills/`

If a skill exists in `{workspace_dir}/bootstrap/skills/`, you MUST treat it as the starting transferable prior for this task.

Use it like this:

1. Read the bootstrap skill before creating iteration-1 strategies.
2. Separate task-specific assumptions from reusable guidance.
3. Preserve the reusable core if it still matches this task family.
4. Explicitly test where the prior does NOT transfer.
5. Your goal is not just to solve the current training task; it is to update the skill so it is more reusable for the next related task in the chain.

Do NOT blindly replay the bootstrap skill. Use it as a prior, then explore targeted overlays that test transfer boundaries."""

    skill_name_section = ""
    if fixed_skill_name:
        skill_name_section = f"""

### Shared Skill Identity — CRITICAL

This task is part of a KernelBench-style kernel optimization chain. Use the fixed shared skill name:

- `{fixed_skill_name}`

Requirements:

1. Keep this exact skill name across all iterations and across tasks in the chain.
2. Do NOT rename the skill based on the current architecture, model family, or local optimization tactic.
3. Treat the skill as one evolving shared artifact. Add architecture-specific guidance as branches inside the same skill instead of creating a new skill identity.
4. Preserve transferable assets from prior tasks by default:
   - reusable scripts in `scripts/`
   - accumulated failure lessons and successful contrasts in `references/`
   - architecture- or verifier-level decision rules in `SKILL.md`
5. Only remove older guidance when current trace evidence shows it is wrong, unsafe, or dominated by a better conditional rule."""

    return f"""## Task: {task_name}

### Benchmark
You are running on **{benchmark_name}** via the Harbor adapter. Read `{workspace_dir}/skill-evolver/benchmarks/harbor/README.md` for adapter details.
Also read:
- `{workspace_dir}/skill-evolver/references/skill-writing-guide.md`
- `{workspace_dir}/skill-evolver/references/skill-template.md`

Do this before writing or updating any skill.

For this run:
- `N_ITERATIONS = {max_iterations}`
- `N_EXPLORE = {n_exploration}` per iteration
- `N_VALIDATE = {n_validation}`

### Task Instruction
```
{instruction}
```

### Environment (Dockerfile)
```dockerfile
{dockerfile}
```

### Workspace
Your workspace is: {workspace_dir}
Task context is in: {workspace_dir}/task/
{train_split_section}
{bootstrap_section}
{skill_name_section}
{reward_mode_section}
### Core Loop

For each iteration `k = 1 .. {max_iterations}`:

1. Prepare `strategy-hints/{skill_name_ref}/`
2. Run exploration
3. Archive the exploration outputs into iteration-specific workspace paths
4. Analyze traces
5. Write the updated skill to `iteration-<k>/skills/{skill_name_ref}/`

### Skill Content Contract

Every updated skill must aim to contain:

1. atomic operations
2. historical failure lessons
3. successful contrasting lessons
4. concrete conditional decision rules
5. explicit anti-overfitting guidance
6. preserved transferable assets from earlier tasks unless disproven by new evidence

Directory placement rules:

- put reusable executable helpers under `<skill-dir>/scripts/`
- put accumulated lessons, contrasts, and evidence under `<skill-dir>/references/`
- keep `SKILL.md` compact and use it as the routing + decision layer
- keep old scripts, references, and failure lessons when they remain valid; refine or annotate them instead of deleting them reflexively

Do NOT let the skill collapse into:

- a single-task implementation recipe
- a benchmark walkthrough
- a pile of rigid prohibitions with no conditions
- one giant end-to-end script that replaces agent reasoning
- a brand new architecture-specific skill that discards previously useful cross-task knowledge

### Exploration Command (use this in EVERY iteration)

```
python {script} --task {task_name} --phase exploration --workspace {workspace_dir} --skill-dir strategy-hints/{skill_name_ref} --model {model} --n-attempts {n_exploration}{tmux_flag}{tasks_dir_flag}
```

### Required Iteration Archival Step

The runner overwrites `task/exploration-results.json` and `task/exploration-traces/` every iteration. After each exploration run, archive them before continuing:

```bash
cp {workspace_dir}/task/exploration-results.json {workspace_dir}/task/iteration-<k>-exploration-results.json
rm -rf {workspace_dir}/task/iteration-<k>-exploration-traces
cp -r {workspace_dir}/task/exploration-traces {workspace_dir}/task/iteration-<k>-exploration-traces
```

### Iteration Semantics

- Iteration 1: build strategy variants from the task and your decision axes. If a bootstrap skill exists, read it first and design strategies that test what transfers, what breaks, and what should be generalized.
- Iteration 2 and later: every trial must read the previous iteration skill first, then apply a different strategy overlay. Do NOT send the exact same skill unchanged to all exploration trials.
- Before each exploration run, write a short comparison table showing how the strategy variants differ.
- When a previous task left reusable scripts, references, or failure logs, test whether they still apply before replacing them. Prefer extending the shared skill with new branches over overwriting it around the latest task only.

### Cross-Task Transfer Objective

At every skill update, prefer instructions that are likely to transfer to a related future task:

- prefer architectural patterns over task-instance constants
- prefer decision rules over one-off recipes
- prefer runtime discovery of files, shapes, and constraints over hardcoded assumptions
- keep any aggressive optimization only if traces show it survives verifier constraints reliably
- preserve reusable failure lessons and success contrasts when they still apply
- preserve reusable scripts and helper workflows when they encode repeatable operations that can help future tasks
- preserve failure lessons even when they come from a different architecture, if the underlying constraint is verifier-, precision-, memory-, or tooling-related
- rewrite local fixes into conditional decision rules whenever possible
- when adding task-local guidance, isolate it behind clear conditions instead of rewriting the whole skill around one task

When deciding between two skills with similar reward, prefer the one with lower overfitting risk and clearer transfer semantics.

### Finalize

After iteration {max_iterations}, choose the best skill version based on reward quality, robustness, token efficiency, and generalization risk. Use the active reward signal mode from this run (or from `task/exploration-results.json` if the run is in auto mode). Copy that version to:

`{workspace_dir}/output/skills/{skill_name_ref}/`

Before finalizing, verify that the chosen skill:

- has a domain-agnostic structure
- would still be useful on a related but different task
- does not mostly consist of one task's implementation details
- contains decision rules in "when X, do Y" form
- separates historical failures from proven successful patterns
- retains still-valid transferable scripts, lessons, and evidence from earlier tasks in the chain

Do not run any extra benchmark calls during Finalize.

### Validation Command

```
python {script} --task {task_name} --phase validation --workspace {workspace_dir} --skill-dir output/skills/{skill_name_ref} --model {model} --n-attempts {n_validation}{tmux_flag}
```

### IMPORTANT: After Validation, STOP

After the validation command returns, output exactly "PIPELINE COMPLETE" as your final message and end your session.
Do NOT read validation traces. Do NOT run more experiments. Do NOT try to improve the skill afterward.

### Start
Read {workspace_dir}/skill-evolver/SKILL.md and begin with Initialize."""
