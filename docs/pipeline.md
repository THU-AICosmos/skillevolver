# Pipeline overview

The agent runs an explore → analyze → update loop end-to-end in a single
Agent SDK session. The same loop handles discrete and continuous reward signals;
the active mode is set per task via `--reward-signal-mode` or inferred from the
benchmark.

## High-level flow

```
                  +---------------------------+
  task instr. →   |   Section 1: Understand   |   read instruction, set up
                  +---------------------------+
                              ↓
                  +---------------------------+
                  |  Section 2: Loop (N=2)    |   for k = 0..N-1:
                  |   - build skill dir       |     • write strategy hints
                  |   - explore (4 trials)    |     • run parallel Harbor trials
                  |   - analyze traces        |     • read JSONL → markdown
                  |   - distill / refine skill|     • merge winners' patterns
                  +---------------------------+
                              ↓
                  +---------------------------+
                  |  Section 3: Finalize      |   choose best skill snapshot
                  +---------------------------+
                              ↓
                  +---------------------------+
                  |  Section 4: Validate      |   run 5 trials on val split
                  +---------------------------+
                              ↓
                       PIPELINE COMPLETE
```

## Trial counts and cost

Per task, the default budget is **$30 / 200 turns**, which covers:

- 2 iterations × 4 exploration trials = 8 trials
- 5 validation trials
- 13 Harbor trials per task

Empirical cost per task ≈ $2 agent + $8 Harbor ≈ $10.

## Train / test split

To prevent the agent from memorizing surface-level features, exploration runs
on `tasks-train/<task>/` (a generated variant of the task) and validation runs
on `tasks/<task>/` (the canonical task). A skill that hardcodes training
filenames or values fails validation.

## Anti-cheating

Three independent layers:

1. **Source isolation** — `tasks-train/<task>/environment/skills/` is removed
   at source. The agent never sees a curated training skill.
2. **PreToolUse path guard** — `agent/guards.py` whitelists the workspace,
   blocks `..` traversal in Bash and path tools, and trips on a deny-list of
   forbidden substrings.
3. **Oracle Peek Audit** — `scripts/aggregate_results.py` greps each
   `agent.log` for reads of `train-context/solution/` and
   `train-context/tests/test_outputs.py`. Tasks where the trace-distillation
   variant beats the baseline without any oracle read are tagged
   `clean_lift`. Reading the training oracle is allowed (it's training labels
   by construction); the audit defends the headline against post-hoc
   "you're leaking" critiques.

## Reward signal modes

| Mode | When to use | Example benchmark |
|------|-------------|-------------------|
| `discrete` | Binary pass/fail task | SkillsBench |
| `continuous` | Scalar reward (speedup, score, etc.) | KernelBench |
| `auto` | Inferred from the benchmark adapter at runtime | mixed sweeps |

Set via `--reward-signal-mode` on `python -m agent.run`, or leave on `auto` and
let the benchmark adapter decide.

## Where things live at runtime

```
evolved-skills/<version>/<task>/<timestamp>/
├── task/
│   ├── instruction.md, Dockerfile, task-data/
│   ├── exploration-traces/trial-NN-{pass,fail}.md
│   ├── train-context/                  # copied after first explore
│   └── validation-traces/
├── strategy-hints/<skill>/             # explore strategy files
├── iteration-0/skills/<skill>/         # first iteration snapshot
├── iteration-1/skills/<skill>/         # second iteration snapshot
├── output/skills/<skill>/              # final skill (gets deployed)
├── agent.log
└── result.json
```

The final skill in `output/skills/` is auto-deployed to
`Benchmarks/skillsbench/tasks-evolved-skills/<task>/environment/skills/` for
validation.
