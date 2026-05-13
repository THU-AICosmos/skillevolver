# KernelBench integration

A thin Harbor-compatible wrapper around selected
[KernelBench](https://github.com/ScalingIntelligence/KernelBench) problems.

The goal is not to rewrite KernelBench. Instead, it packages a KernelBench
problem as a Harbor task so the self-evolving-skills pipeline can:

- load a problem as a task directory
- ask an agent to produce a `ModelNew` implementation
- run a verifier inside a task container
- store traces and rewards in standard Harbor job outputs

## Layout

- `harbor_converter.py` — converts one local KernelBench problem into a Harbor task
- `tasks-train/` — generated Harbor task directories
- `generated/` — optional scratch output when running the converter manually

## Prerequisites

Clone KernelBench locally (default expected location: `$HOME/KernelBench`):

```bash
git clone https://github.com/ScalingIntelligence/KernelBench.git "$HOME/KernelBench"
```

Or set `KERNELBENCH_ROOT` to point at your existing checkout.

## Convert a problem to a Harbor task

From the repository root:

```bash
python Benchmarks/kernelbench/harbor_converter.py \
  --kernelbench-root "${KERNELBENCH_ROOT:-$HOME/KernelBench}" \
  --level 1 \
  --problem-id 1 \
  --output-dir Benchmarks/kernelbench/generated
```

This writes a Harbor task directory into `Benchmarks/kernelbench/generated/`.
Move the directory under `Benchmarks/kernelbench/tasks-train/` to run it with
the agent.

## Build the task container

```bash
TASK_NAME=kb-l1-p1-square-matrix-multiplication \
  bash Benchmarks/kernelbench/build_image.sh
```

By default the image is built locally (`docker buildx --load`). Override
`IMAGE_REPO`, `IMAGE_TAG`, `PUSH=1`, or `BUILDER` for a custom registry / build
cluster.

## Notes

- The converter targets local KernelBench problems on disk.
- The generated task uses a CPU-only verifier as a minimal integration point.
- For full KernelBench-style GPU compilation and performance scoring, extend
  the generated verifier to invoke KernelBench's evaluation scripts inside a
  CUDA-capable container.
