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

`scripts/run_eval.sh` auto-discovers every task under `bench-assets/tasks-train/`
and runs them in order. Open two tmux windows — one for the agent, one for
Harbor — then launch:

```bash
# In the agent window
bash scripts/run_eval.sh harbor:0 1 4     # tasks 1-4

# In a second agent window, in parallel
bash scripts/run_eval.sh harbor:1 5 8     # tasks 5-8

# Or pass an explicit list:
TASKS=offer-letter-generator,court-form-filling bash scripts/run_eval.sh harbor:0
```

The first positional arg is the Harbor tmux window. The agent's
`run_and_wait.py` uses `tmux send-keys` to dispatch Harbor commands there.
Each task costs ≈ $10 and takes ≈ 30 min, so size the index range accordingly.

Note that several SkillsBench tasks require paid third-party APIs (e.g.
hosted LLM/STT services) which the agent cannot use; those will fail at
exploration time. The OSS release does not curate a "runnable subset" — you
can either start from a small explicit `TASKS=` list, or run the full sweep
and ignore the API-dependent failures in the aggregated report.

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

Writes `evolved-skills/<version>/report.md` and `results-db.jsonl` per
pipeline version, and runs the Oracle Peek Audit described in
[docs/pipeline.md](pipeline.md).

## Train/test split

Validation runs on `Benchmarks/skillsbench/tasks/<task>/` (canonical, immutable).
Exploration runs on `Benchmarks/skillsbench/tasks-train/<task>/` — generated
training variants with different filenames and values. The source of truth for
training variants is `bench-assets/tasks-train/<task>/`; `scripts/setup.sh`
mirrors it into `Benchmarks/skillsbench/tasks-train/` for the benchmark
runner. If you edit a variant under `bench-assets/` (or use
`tools/generate_train_variant.py` to make a new one), re-run `setup.sh` or
just:

```bash
rsync -a --delete bench-assets/tasks-train/ Benchmarks/skillsbench/tasks-train/
```
