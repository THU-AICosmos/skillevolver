---
name: skill-evolver
description: Evolve reusable agent skills through a repeated three-phase loop of
  exploration, trace analysis, and skill update. Works on benchmarks with
  parallel trial execution and pass/fail or scalar reward feedback.
---

# SkillEvolver v2

SkillEvolver v2 uses one repeated loop. There is no special "first creation" phase and no separate "refine" concept. Every iteration uses the same three phases:

1. **Exploration**: run parallel trials on the training task using strategy variants derived from the current skill state
2. **Analyze Traces**: read the traces and results, identify what the current skill missed or what unnecessary detours it still allows
3. **Update Skill**: write the next skill version, preserving what works and adding the missing guidance

After the configured number of iterations, pick the best version and run final validation on unseen data.

## Reward Signals

This workflow supports both:

- **discrete signals**: thresholded pass/fail feedback
- **continuous signals**: scalar reward, speedup, score, or proxy reward

The benchmark adapter determines which mode is active for the current run.

- If `signal_mode = "continuous"`, treat raw scalar reward as the primary optimization signal and use binary pass/fail only as a secondary sanity check.
- If `signal_mode = "discrete"`, treat pass/fail as the primary optimization signal and use raw reward only as a tie-breaker or ordering hint.

Do not assume every benchmark has meaningful binary pass labels. On optimization-heavy tasks such as KernelBench, continuous reward may be the only signal that aligns with the benchmark objective.

## Core Principle

Every iteration must do fresh exploration.

When a bootstrap skill from a previous task is available, treat it as a transfer prior, not as ground truth. The purpose of the loop is to improve a skill that can survive across related tasks, not just to maximize reward on one training instance.

The agent must NOT do:
- one initial exploration to create `v1`
- then only re-run the exact same skill in later rounds

Instead, for each iteration `k`, the agent must:
- start from the current skill `v_{k-1}` (or no skill for iteration 1)
- generate a small set of strategy variants that deliberately test different choices, constraints, or emphases
- run those variants in parallel
- use the resulting traces to produce `v_k`

The loop is therefore:

`current skill -> strategy variants -> exploration -> trace analysis -> updated skill`

## Benchmark Adapters

Benchmark-specific execution details live in `benchmarks/<benchmark>/README.md`.

Read the adapter README before running any trials. The README tells you:
- how many iterations to run
- how many exploration trials per iteration
- how to pass strategy hints into parallel trials
- where traces and results are written
- how to run final validation

---

## Loop Structure

Assume the adapter README defines:
- `N_ITERATIONS`
- `N_EXPLORE`
- `N_VALIDATE`

Then the required workflow is:

1. **Initialize**
2. For `k = 1 .. N_ITERATIONS`:
   - Phase A: Exploration
   - Phase B: Analyze Traces
   - Phase C: Update Skill
3. **Finalize**
4. **Validate**

There is no additional benchmark call between the last update and validation.

---

## Initialize

Read the task instruction, environment, and relevant input files. Identify decision axes:
- library choice
- algorithm choice
- output formatting / schema assumptions
- precision / performance tradeoffs
- domain-specific edge cases

Do only enough exploration here to understand the task. Do not solve the task in this phase.

Create a workspace layout like:

```text
strategy-hints/
iteration-1/skills/<skill-name>/
iteration-2/skills/<skill-name>/
...
output/skills/<skill-name>/
```

Use a stable `<skill-name>` across all iterations.

If this run is part of a cross-task chain, keep the same shared skill name across tasks as well. Do not rename the skill just because the current task belongs to a different architecture family.

For KernelBench cross-task runs, use the fixed shared name:

- `kernel-optim`

Before writing any skill content, read:
- `references/skill-writing-guide.md`
- `references/skill-template.md`

The final skill is not allowed to be an ad-hoc task recipe. It must be a reusable artifact that can survive a task family shift such as:
- kernel -> different kernel
- algorithmic optimization -> different algorithmic optimization
- office/doc task -> different office/doc task

This means the skill must capture portable operations and decision rules, not just instructions for one benchmark instance.

---

## Phase A: Exploration

Run fresh exploration every iteration.

### Iteration 1

There is no prior skill yet. Create strategy variants from:
- the task instruction
- your decision-axis enumeration
- any quick, cheap experiments that clarify a real branch

If `bootstrap/skills/` contains a previously evolved skill, Iteration 1 must start from that prior:
- read the bootstrap skill first
- identify which rules seem architecture-level and reusable
- identify which rules may be task-instance-specific
- create variants that explicitly test transfer boundaries
- preserve the prior skill's reusable scripts, references, and failure lessons unless current evidence disproves them
- extend the prior skill with clearer conditional branches instead of replacing it with a new architecture-specific identity

### Iteration k > 1

You already have `v_{k-1}`. Do NOT send that exact same skill unchanged to all trials.

Instead, derive multiple strategy variants from `v_{k-1}`. Each variant should keep the current skill's core lessons while testing one meaningful change, such as:
- a stricter constraint
- an alternative library choice
- a different algorithmic shortcut
- a different failure-avoidance rule
- a different performance/correctness tradeoff
- a reduced or expanded set of instructions

The purpose is to probe the neighborhood of the current skill, not to replay it verbatim.

Across tasks, the purpose is to evolve a skill that remains useful on the next related task in the chain. Favor updates that convert brittle heuristics into reusable decision rules.
Across heterogeneous tasks, prefer additive branching inside one shared skill over wiping the skill and rebuilding it around the latest task only.

### Strategy Format

Create one strategy skill directory for the current iteration:

```text
strategy-hints/<skill-name>/
├── SKILL.md
└── references/
    ├── strategy-0.md
    ├── strategy-1.md
    ├── strategy-2.md
    └── strategy-3.md
```

The shared `SKILL.md` must instruct each trial to:
- read the current strategy file for its trial index
- treat that file as the initial operating hypothesis
- still adapt if the environment proves the hypothesis wrong

For iterations `k > 1`, the shared `SKILL.md` must also tell the agent to read the current skill `v_{k-1}` first, then apply the iteration-specific strategy variant as an overlay.

### Diversity Requirement

Before launching trials, write a comparison table showing how the variants differ across the main axes. No two strategies may be identical on all axes.

### Run

Use the exploration command from the benchmark adapter README. Exploration always runs on the training task variant.

---

## Phase B: Analyze Traces

After each exploration run, read enough traces to cover:
- every distinct success mode
- every distinct failure mode
- any passing run that still wastes tokens or takes avoidable detours

Answer these questions:

1. What did the best trials know that weaker trials did not?
2. Which guidance in the current skill was actually useful?
3. Which guidance was ignored, too weak, too vague, or actively misleading?
4. What new instruction would have prevented the observed failures?
5. What existing instruction should be tightened, simplified, or removed?
6. Which parts of the current or bootstrap skill seem too specific to this task and should be generalized before the next task?
7. Which older scripts, lessons, and failure notes are still transferable and should be kept intact for the next task?

When available, use training-task tests or oracle material only to resolve real uncertainty. Do not overfit to training-specific constants, filenames, or schemas.

---

## Phase C: Update Skill

Write the next skill version as a patch over the current one.

Rules:
- preserve what already works
- preserve what still looks transferable even if it was learned on a previous task
- add only the minimum new guidance needed to explain the trace evidence
- remove or weaken instructions that consistently push trials into dead ends
- keep the skill reusable for a future instance, not just this training case
- when a rule only works for the current task shape, model variant, or file naming pattern, rewrite it as a conditional decision rule or remove it
- do not delete reusable scripts, contrasts, or failure lessons unless current evidence shows they are wrong, unsafe, or dominated by a clearer conditional rule
- prefer refining the existing shared skill over renaming or replacing it with a task-family-specific skill

### Required Skill Contents

Every evolved skill must contain the following components.

1. **Atomic operations**
   - Small reusable scripts or code snippets that do one thing only
   - Example: recalculate formulas, parse a binary header, check state_dict compatibility, benchmark a candidate kernel
   - These belong under `<skill-dir>/scripts/` when they save repeated boilerplate
   - When inherited from an earlier task, keep them if they encode a reusable operation even if the current task does not need them immediately

2. **Historical failure lessons**
   - A compact list of failure patterns actually observed in traces
   - Each lesson must say what went wrong and why it matters
   - Do not write generic warnings without trace evidence
   - These belong in `<skill-dir>/references/` if they are longer than a short summary in `SKILL.md`
   - Preserve old failure lessons when the underlying constraint can recur across tasks, such as verifier quirks, precision failures, compile instability, or state_dict compatibility rules

3. **Successful contrasting lessons**
   - For each important failure mode, describe the contrasting successful pattern when available
   - Prefer paired contrasts: "failed because X; succeeded when Y"
   - Put reusable contrasts and detailed evidence in `<skill-dir>/references/`

4. **Atomic decision rules**
   - Express guidance in conditional form
   - Preferred style: "When you need X and constraints Y hold, do Z"
   - Each rule should be as local and reusable as possible

5. **Explicit anti-overfitting guard**
   - State what should NOT be copied from the current task
   - Example: filenames, exact dimensions, one benchmark's verifier quirks, one dataset's constants

### Forbidden Skill Contents

Do NOT let the evolved skill become any of the following:

- a verbatim implementation of the current task
- a single end-to-end task script that removes all agent reasoning
- a benchmark-instance walkthrough with task-specific filenames and constants
- a list of absolute prohibitions that are not conditioned on observed constraints
- a domain-locked document that only makes sense for kernels, or only for office tasks, or only for one subfamily

### Preferred Final Skill Shape

Use a consistent structure like:

```markdown
# <Skill Title>

## What This Skill Is For
## Atomic Operations
## Failure Lessons
## Success Patterns
## Decision Rules
## Anti-Patterns / Do Not Overfit
## References
```

This structure is intentionally domain-agnostic. The same sections should work for kernels, algorithms, office tasks, and other benchmark families.

### Directory Convention

Within any skill directory:

- `<skill-dir>/scripts/`
  - atomic reusable tools
  - helper programs the agent can invoke directly

- `<skill-dir>/references/`
  - failure histories
  - success/failure contrasts
  - supporting evidence
  - API notes, format notes, and domain gotchas

- `<skill-dir>/SKILL.md`
  - the compact front door
  - summary decision rules
  - links to the right script/reference files

Do not dump all history and all implementation detail into `SKILL.md`. Use `SKILL.md` as the index and decision layer.

Write the updated skill to:

```text
iteration-<k>/skills/<skill-name>/SKILL.md
```

If the skill also needs scripts, place them under:

```text
iteration-<k>/skills/<skill-name>/scripts/
```

The scripts must be reusable procedures, not hardcoded answers from the current task.

If there is no good atomic script to bundle, say so explicitly in your trace analysis and explain why the skill should remain markdown-only for that task family.

---

## Finalize

After the last iteration, choose which iteration becomes the final exported skill.

Choose based on:
- training pass rate
- reward quality
- token efficiency
- robustness across the trace set
- generalization risk
- likely usefulness as the starting prior for the next related task

Then copy the chosen version to:

```text
output/skills/<skill-name>/
```

Finalize is agent reasoning only. Do not launch extra benchmark runs here.

---

## Validate

Run final validation once, using the chosen skill from `output/skills/<skill-name>/`.

Validation runs on the held-out task variant defined by the benchmark adapter. After validation returns, stop.

---

## Hard Rules

- Every iteration must include exploration
- Later iterations must explore strategy variants derived from the current skill
- Do not collapse all later iterations into "run the same skill again"
- Do not call Harbor directly if the adapter says to use a runner script
- Do not read held-out validation data unless the adapter explicitly allows it
- Do not encode training-instance-specific constants into the final skill
- Do not add extra benchmark calls outside the configured loop and final validation
