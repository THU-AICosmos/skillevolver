# Harbor adapter

This adapter wires SkillEvolver to any benchmark that runs on
[Harbor](https://github.com/benchflow-ai/harbor) — currently SkillsBench and
KernelBench. It is **benchmark-agnostic** at the script level: the
`--task <name>` argument is whatever Harbor-compatible task directory you want
to run.

SkillEvolver uses a single repeated loop:

1. `exploration`
2. `analyze traces`
3. `update skill`

There is no special "first distill" phase and no separate "refine" phase in the method. Every iteration uses exploration on the training task, even after a skill already exists.

This adapter also supports chained cross-task evolution:

- task `T1` produces an exported skill
- task `T2` starts from that skill as a bootstrap prior
- the process repeats across a sequence of related tasks

In chained runs, the agent should improve the skill for the current task while preserving or strengthening guidance that is likely to transfer to the next related task.

The adapter assumes the evolved skill is a reusable knowledge artifact, not a task-local implementation note. In practice this means:

- the skill should contain atomic reusable operations
- the skill should preserve trace-backed failure lessons
- the skill should contrast successful and failed patterns
- the skill should express recommendations as conditional decision rules
- the skill should avoid task-instance implementation details unless they are rewritten into general rules

When drafting or revising a skill, read:

- `skill-evolver/references/skill-writing-guide.md`
- `skill-evolver/references/skill-template.md`

## Task Format

The two supported benchmarks lay tasks out differently:

| Benchmark | Validation tasks | Training tasks | Source of truth |
|-----------|------------------|----------------|------------------|
| SkillsBench | `Benchmarks/skillsbench/tasks/<task>/` | `Benchmarks/skillsbench/tasks-train/<task>/` | `bench-assets/tasks-train/<task>/` (mirrored into the submodule by `scripts/sync_tasks_train.sh`) |
| KernelBench | none — same Dockerfile + verifier each trial | `Benchmarks/kernelbench/tasks-train/<task>/` | upstream KernelBench, converted via `Benchmarks/kernelbench/harbor_converter.py` |

Each task contains:
- `instruction.md`
- `environment/Dockerfile`
- task data files
- hidden oracle and tests not directly exposed to the evolving agent unless copied into workspace by the runner

Task names are passed verbatim via `--task`. Tasks starting with `kb-` are
treated as KernelBench tasks: the pipeline uses the fixed shared skill name
`kernel-optim` (designed for cross-kernel transfer) and the prompt switches to
continuous-reward semantics.

## Iteration Configuration

Defaults (override via `--iterations`, `--n-exploration`, `--n-validation`):

| Parameter | Value | Meaning |
|---|---|---|
| `N_ITERATIONS` | **3** | Run three exploration-analysis-update loops on the training task |
| `N_EXPLORE` | **4** | Four parallel exploration trials per iteration |
| `N_VALIDATE` | **5** | Five final validation trials on the evaluation task |

Total Harbor invocations per task: **4**:
- iteration 1 exploration
- iteration 2 exploration
- iteration 3 exploration
- final validation

## What Changes Across Iterations

### Iteration 1

Exploration is driven by task-derived strategy variants only, unless the workspace contains `bootstrap/skills/`.

If `bootstrap/skills/` exists, iteration 1 must:
- read the bootstrap skill first
- derive strategy variants that test what transfers cleanly and what fails on the new task
- treat the bootstrap skill as a prior, not as an immutable recipe

### Iteration 2 and 3

Exploration must be driven by:
- the current skill from the previous iteration
- plus fresh strategy variants built on top of that skill

This means every exploration trial in later iterations should:
- read the current skill first
- read its assigned strategy overlay second
- try a distinct variant of the current skill rather than replaying the same instructions unchanged

## Running Trials

All benchmark execution must go through `scripts/run_and_wait.py`. Do not call Harbor directly.

The runner:
1. deploys the specified skill into the task variant when `--skill-dir` is provided
2. launches Harbor with parallel trials
3. waits for completion
4. preprocesses traces
5. writes `<workspace>/task/<phase>-results.json`

## Exploration Command

Use this for **every** iteration, including iterations 2 and 3:

```bash
python <skill-evolver>/benchmarks/harbor/scripts/run_and_wait.py \
  --task <task-name> \
  --phase exploration \
  --workspace <workspace> \
  --skill-dir strategy-hints/<skill-name> \
  --model claude-opus-4-6 \
  --n-attempts 4 \
  --tmux-window skillsbench:1 \
  --tasks-dir tasks-train
```

Interpretation:
- iteration 1: `strategy-hints/<skill-name>/` contains task-derived strategies only
- iteration 2+: `strategy-hints/<skill-name>/` must instruct trials to read `iteration-{k-1}/skills/<skill-name>/SKILL.md` first, then apply their strategy overlay

In other words, later exploration still uses `--phase exploration`, not `refine`.

## Validation Command

After the final iteration, validate the chosen output skill:

```bash
python <skill-evolver>/benchmarks/harbor/scripts/run_and_wait.py \
  --task <task-name> \
  --phase validation \
  --workspace <workspace> \
  --skill-dir output/skills/<skill-name> \
  --model claude-opus-4-6 \
  --n-attempts 5 \
  --tmux-window skillsbench:1
```

## Workspace Layout

Recommended layout:

```text
strategy-hints/<skill-name>/
iteration-1/skills/<skill-name>/
iteration-2/skills/<skill-name>/
iteration-3/skills/<skill-name>/
output/skills/<skill-name>/
task/exploration-results.json
task/exploration-traces/
task/validation-results.json
```

`task/exploration-results.json` and `task/exploration-traces/` are overwritten each iteration by the runner, so if the agent wants a persistent summary it should record iteration-specific notes in its own workspace files.

## Reward Signal Modes

`skill-evolver` supports both discrete and continuous reward signals.

- `SKILLSBENCH_REWARD_SIGNAL_MODE=discrete`
  Uses thresholded pass/fail as the primary analysis signal.
- `SKILLSBENCH_REWARD_SIGNAL_MODE=continuous`
  Uses `raw_reward` / `mean_reward` as the primary analysis signal and treats pass/fail as secondary bookkeeping.
- `SKILLSBENCH_REWARD_SIGNAL_MODE=auto`
  Chooses `discrete` only when all observed rewards are binary `0/1`; otherwise chooses `continuous`.

Secondary binarization is controlled by:

- `SKILLSBENCH_PASS_REWARD_MIN`

The runner writes both values into `task/*-results.json`:

- `signal_mode`
- `pass_reward_min`

In continuous mode, traces are ranked by `raw_reward`, and the agent should reason from the strongest and weakest trajectories directly instead of optimizing for pass rate.

## Strategy Routing

Parallel exploration uses `HARBOR_TRIAL_INDEX`.

Create:

```text
strategy-hints/<skill-name>/
├── SKILL.md
└── references/
    ├── strategy-0.md
    ├── strategy-1.md
    ├── strategy-2.md
    └── strategy-3.md
```

The shared `SKILL.md` should route by:

```bash
cat $(find /root/.claude/skills -name "strategy-$HARBOR_TRIAL_INDEX.md" -path "*/references/*")
```

For iterations 2+, the shared `SKILL.md` should also tell the agent to read the previous iteration skill before reading the strategy file.

## Training Ground Truth

After exploration completes in train-split mode, the runner may copy training context into:

```text
<workspace>/task/train-context/
```

Use this only to resolve genuine uncertainty. Prefer traces first. Avoid overfitting to training-specific constants.

## Cross-Task Preference

When this adapter is used in a multi-task chain, prefer skills that:

- keep one stable shared identity across tasks instead of renaming by architecture family
- encode architectural or verifier-relevant decision rules
- avoid task-instance-specific filenames and constants
- make runtime discovery steps explicit
- keep aggressive optimizations conditional on observed correctness stability
- preserve reusable scripts, helper workflows, failure lessons, and evidence from earlier tasks unless contradicted by new traces

When two skills have similar train reward, choose the one that is more likely to survive the next related task.

For KernelBench multi-task chains, use the fixed shared skill name:

- `kernel-optim`

Treat architecture-specific guidance as branches within `kernel-optim`, not as separate skill identities such as CNN-only, RNN-only, or attention-only skills.

## Skill Content Requirements

Every final skill should be checkable against this rubric:

1. `Atomic Operations`
   - includes small reusable scripts or snippets for repeated mechanical steps
   - these should live under `<skill-dir>/scripts/`
   - avoids one giant end-to-end solver script
   - preserve inherited reusable scripts when they still encode portable operations

2. `Failure Lessons`
   - records real trace-backed failure modes
   - names the observable symptom and the root cause
   - detailed lessons should live under `<skill-dir>/references/`
   - preserve inherited failure lessons when the underlying issue can recur across tasks

3. `Success Patterns`
   - contrasts what worked against what failed
   - avoids unsupported claims like "always do X" unless repeated evidence supports it
   - detailed contrasts should live under `<skill-dir>/references/`

4. `Decision Rules`
   - uses conditional language
   - example: "When strict state_dict loading is present, preserve module names and parameter keys exactly"

5. `Anti-Overfitting Guard`
   - explicitly bans task-specific filenames, constants, and benchmark-local assumptions from becoming the skill

If a candidate final skill is mostly a task walkthrough, mostly a list of rigid prohibitions, or mostly a concrete implementation recipe for one benchmark item, treat that as a low-quality skill even if its train reward is acceptable.

Also treat it as low quality if it throws away still-valid scripts, evidence, and failure lessons from earlier tasks just because the latest task belongs to a different model family.

In short:

- executable reusable operations -> `scripts/`
- accumulated experience and evidence -> `references/`
- compact reusable guidance and routing -> `SKILL.md`

## Known Quirks

- Trial collection can race with Harbor result flushing; compare requested vs collected trial counts
- Permissions and tmux/window setup still follow the same Harbor constraints as the original adapter
- Because exploration is repeated every iteration, cost will be higher than the original evolver design
