# Running KernelBench

[KernelBench](https://github.com/ScalingIntelligence/KernelBench) tasks are
adapted into Harbor-compatible task directories so the agent can optimize a
single GPU kernel per task. KernelBench provides continuous reward (speedup
ratio), so KernelBench runs use `--reward-signal-mode continuous`.

## Prerequisites

Clone KernelBench upstream:

```bash
git clone https://github.com/ScalingIntelligence/KernelBench.git "$HOME/KernelBench"
# Or set KERNELBENCH_ROOT to an existing checkout
```

## Convert a problem to a Harbor task

```bash
python Benchmarks/kernelbench/harbor_converter.py \
  --kernelbench-root "${KERNELBENCH_ROOT:-$HOME/KernelBench}" \
  --level 1 \
  --problem-id 1 \
  --output-dir Benchmarks/kernelbench/tasks-train
```

A converted task is named `kb-l<level>-p<id>-<slug>` and lives at
`Benchmarks/kernelbench/tasks-train/<task-name>/`.

## Build the task container

```bash
TASK_NAME=kb-l1-p1-square-matrix-multiplication \
  bash Benchmarks/kernelbench/build_image.sh
```

By default the image is loaded into the local Docker daemon. Override
`IMAGE_REPO`, `IMAGE_TAG`, `PUSH=1`, or `BUILDER` for a custom registry / build
cluster.

## Run the agent on one KernelBench task

```bash
python -m agent.run \
  --task kb-l1-p1-square-matrix-multiplication \
  --reward-signal-mode continuous \
  --model claude-opus-4-6
```

With `--reward-signal-mode continuous`, the pipeline reads continuous reward
(speedup vs. reference) from each Harbor trial and uses it to rank candidate
kernels during distillation.

## Shared skill identity: `kernel-optim`

Any `--task` whose name starts with `kb-` triggers a KernelBench-specific code
path in the agent prompt: the skill is **always named `kernel-optim`**, not
named after the current task.

This is deliberate. A skill for "matrix multiplication on level 1" should also
help on "convolution on level 2" — the reusable knowledge (tiling, shared
memory, register pressure, verifier constraints) transfers across kernels.
Naming each task's skill differently would defeat that.

To chain KernelBench tasks together — bootstrap each run from the previous
task's output skill:

```bash
# First task
python -m agent.run --task kb-l1-p1-... --reward-signal-mode continuous

# Subsequent task, seeded from the first
python -m agent.run --task kb-l1-p2-... --reward-signal-mode continuous \
  --seed-skill-dir evolved-skills/evolver/kb-l1-p1-.../<timestamp>/output/skills/kernel-optim
```

The agent reads the seed skill before generating new strategy variants.

## Output

A successful run produces `output/skills/kernel-optim/SKILL.md` containing
the discovered optimization recipe plus any bundled CUDA / Triton
implementation. The validation phase confirms the result on the canonical
test inputs.

## Notes

- The default verifier is CPU-only — useful for correctness checks but does
  not exercise KernelBench's GPU performance scoring. For full GPU scoring,
  extend the generated verifier to call KernelBench's evaluation scripts
  inside a CUDA-capable container.
- There is **no train/test split** — KernelBench doesn't ship one. Exploration
  and validation run on the same problem. To avoid overfitting to the
  training data, the skill is graded on whether its rules generalize, not on
  whether it memorizes one problem's solution.
- See [Benchmarks/kernelbench/README.md](../Benchmarks/kernelbench/README.md)
  for converter details.
