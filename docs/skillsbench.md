# Running SkillsBench

SkillsBench is a 87-task benchmark covering discrete pass/fail tasks across
domains (document processing, data analysis, scheduling, etc.). It lives as a
submodule under `Benchmarks/skillsbench/`.

## One task

```bash
python -m agent.run \
  --task offer-letter-generator \
  --train-split \
  --model claude-opus-4-6
```

Adjust `--iterations` (default 2) to trade off cost vs. quality. `N=1` is the
no-refinement ablation.

## Sweep

`scripts/run_eval.sh` runs the canonical 81-task sweep (the 6 tasks excluded
require paid APIs the agent can't access). Open two tmux windows — one for the
agent, one for Harbor — then launch:

```bash
# In the agent window
bash scripts/run_eval.sh harbor:0 1 8     # tasks 1-8

# In a second agent window, in parallel
bash scripts/run_eval.sh harbor:1 9 18    # tasks 9-18
```

The first positional arg is the Harbor tmux window. The agent's
`run_and_wait.py` uses `tmux send-keys` to dispatch Harbor commands there.

## Re-deploy a previously evolved skill

```bash
python -m agent.run \
  --task offer-letter-generator \
  --deploy-from evolved-skills/evolver/offer-letter-generator/<timestamp>/output/skills/<skill-name>
```

This skips generation and just copies the skill into
`tasks-evolved-skills/<task>/environment/skills/` for validation.

## Aggregate results

After a sweep completes:

```bash
python scripts/aggregate_results.py
```

Writes a cross-task report under `evolved-skills/` and runs the Oracle Peek
Audit described in [docs/pipeline.md](pipeline.md).

## Train/test split

Validation runs on `Benchmarks/skillsbench/tasks/<task>/` (canonical, immutable).
Exploration runs on `Benchmarks/skillsbench/tasks-train/<task>/` — generated
training variants with different filenames and values. The source of truth for
training variants is `bench-assets/tasks-train/<task>/`;
`scripts/sync_tasks_train.sh` mirrors it into the SkillsBench submodule for the
benchmark runner.
