#!/usr/bin/env python3
"""Convert a local KernelBench problem into a Harbor task directory."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path
from typing import Iterable


TASK_TOML_TEMPLATE = '''version = "1.0"

[metadata]
author_name = "OpenAI Codex"
author_email = "noreply@example.com"
difficulty = "medium"
category = "kernel-optimization"
tags = ["kernelbench", "pytorch", "operator-optimization", "correctness", "speedup"]

[verifier]
timeout_sec = 600.0

[agent]
timeout_sec = 900.0

[environment]
build_timeout_sec = 1200.0
cpus = 2
memory_mb = 8192
storage_mb = 12288
gpus = {gpus}
allow_internet = true
'''


TEST_SH = '''#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier
python /tests/verify.py 2>&1 | tee /logs/verifier/verify.log
exit 0
'''


VERIFY_PY = '''import copy
import importlib.util
import json
import time
import traceback
from pathlib import Path

import torch


REFERENCE_PATH = Path("/root/problem.py")
SOLUTION_PATH = Path("/root/generated_kernel.py")
LOG_DIR = Path("/logs/verifier")
REWARD_JSON = LOG_DIR / "reward.json"
REWARD_TXT = LOG_DIR / "reward.txt"


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def clone_value(value):
    if isinstance(value, torch.Tensor):
        return value.detach().clone()
    if isinstance(value, list):
        return [clone_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(clone_value(v) for v in value)
    if isinstance(value, dict):
        return {k: clone_value(v) for k, v in value.items()}
    return copy.deepcopy(value)


def move_to_device(value, device):
    if isinstance(value, torch.Tensor):
        return value.to(device)
    if isinstance(value, list):
        return [move_to_device(v, device) for v in value]
    if isinstance(value, tuple):
        return tuple(move_to_device(v, device) for v in value)
    if isinstance(value, dict):
        return {k: move_to_device(v, device) for k, v in value.items()}
    return value


def normalize_output(value):
    if isinstance(value, torch.Tensor):
        return value.detach().cpu()
    if isinstance(value, list):
        return [normalize_output(v) for v in value]
    if isinstance(value, tuple):
        return tuple(normalize_output(v) for v in value)
    if isinstance(value, dict):
        return {k: normalize_output(v) for k, v in value.items()}
    if hasattr(value, "to_tuple"):
        return tuple(normalize_output(v) for v in value.to_tuple())
    if hasattr(value, "items") and callable(value.items):
        try:
            return {k: normalize_output(v) for k, v in value.items()}
        except Exception:
            pass
    return value


def assert_close_structures(actual, expected, *, rtol=1e-4, atol=1e-4):
    if isinstance(expected, torch.Tensor):
        assert isinstance(actual, torch.Tensor), f"Expected tensor output, got {type(actual)}"
        torch.testing.assert_close(actual, expected, rtol=rtol, atol=atol)
        return
    if isinstance(expected, (list, tuple)):
        assert isinstance(actual, type(expected)), f"Output type mismatch: {type(actual)} vs {type(expected)}"
        assert len(actual) == len(expected), f"Output length mismatch: {len(actual)} vs {len(expected)}"
        for a, e in zip(actual, expected):
            assert_close_structures(a, e, rtol=rtol, atol=atol)
        return
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"Output type mismatch: {type(actual)} vs dict"
        assert actual.keys() == expected.keys(), f"Output keys mismatch: {actual.keys()} vs {expected.keys()}"
        for key in expected:
            assert_close_structures(actual[key], expected[key], rtol=rtol, atol=atol)
        return
    assert actual == expected, f"Output mismatch: {actual!r} vs {expected!r}"


def synchronize(device: str):
    if device == "cuda":
        torch.cuda.synchronize()


def run_model(model, prepared_inputs):
    with torch.inference_mode():
        if isinstance(prepared_inputs, dict):
            return model(**prepared_inputs)
        if isinstance(prepared_inputs, (list, tuple)):
            return model(*prepared_inputs)
        return model(prepared_inputs)


def forward_once(model, base_inputs, device: str):
    prepared_inputs = move_to_device(clone_value(base_inputs), device)
    output = run_model(model, prepared_inputs)
    synchronize(device)
    return normalize_output(output)


def benchmark(model, base_inputs, device: str, warmup: int = 2, repeats: int = 5) -> float:
    for _ in range(warmup):
        forward_once(model, base_inputs, device)

    timings = []
    for _ in range(repeats):
        synchronize(device)
        start = time.perf_counter()
        forward_once(model, base_inputs, device)
        synchronize(device)
        timings.append(time.perf_counter() - start)
    return sum(timings) / len(timings)


def write_reward(reward: float, *, correctness: int, speedup: float, metadata: dict):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    REWARD_TXT.write_text(f"{reward}\\n", encoding="utf-8")
    payload = {
        "reward": reward,
        "correctness": correctness,
        "speedup": speedup,
        **metadata,
    }
    REWARD_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    metadata = {"device": device}

    try:
        if not SOLUTION_PATH.exists():
            raise FileNotFoundError(f"Expected solution file at {SOLUTION_PATH}")

        ref_mod = load_module(REFERENCE_PATH, "reference_problem")
        solution_mod = load_module(SOLUTION_PATH, "candidate_solution")
        if not hasattr(solution_mod, "ModelNew"):
            raise AttributeError("generated_kernel.py must define ModelNew")

        init_inputs = clone_value(ref_mod.get_init_inputs()) if hasattr(ref_mod, "get_init_inputs") else []
        eval_inputs = clone_value(ref_mod.get_inputs()) if hasattr(ref_mod, "get_inputs") else []

        ref_model = ref_mod.Model(*init_inputs).eval().to(device)
        candidate_model = solution_mod.ModelNew(*init_inputs).eval().to(device)
        candidate_model.load_state_dict(ref_model.state_dict(), strict=False)

        expected = forward_once(ref_model, eval_inputs, device)
        actual = forward_once(candidate_model, eval_inputs, device)
        assert_close_structures(actual, expected)

        reference_time = benchmark(ref_model, eval_inputs, device)
        candidate_time = benchmark(candidate_model, eval_inputs, device)
        speedup = max(reference_time / max(candidate_time, 1e-9), 0.0)
        reward = float(speedup)
        metadata.update(
            {
                "reference_time_sec": reference_time,
                "candidate_time_sec": candidate_time,
            }
        )
        write_reward(reward, correctness=1, speedup=float(speedup), metadata=metadata)
    except Exception as exc:
        metadata.update(
            {
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        write_reward(0.0, correctness=0, speedup=0.0, metadata=metadata)


if __name__ == "__main__":
    main()
'''


TEST_OUTPUTS_PY = '''"""Placeholder test module.

Harbor uses tests/test.sh as the verifier entrypoint for converted KernelBench tasks.
This file exists only to keep the task layout familiar and to aid ad-hoc debugging.
"""
'''


def task_slug(problem_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", problem_name.lower()).strip("-")
    return re.sub(r"-+", "-", slug)


def render_instruction(*, level: int, problem_id: int, filename: str, source: str) -> str:
    preview_lines = source.strip().splitlines()
    preview = "\n".join(preview_lines[:40])
    return f'''You are working on a Harbor-wrapped KernelBench task.

Task origin:
- KernelBench level: {level}
- KernelBench problem id: {problem_id}
- Original file: {filename}

Your job is to write an implementation file at:

- `/root/generated_kernel.py`

Requirements:

1. The file must define a class named `ModelNew`.
2. `ModelNew` must preserve the same constructor signature as the reference
   `Model` in `/root/problem.py`.
3. `ModelNew.forward(...)` must preserve the same input and output contract.
4. Correctness is mandatory. Reward is computed as `correctness(0/1) * speedup`.
5. Prefer a valid implementation that is measurably faster only when you can
   preserve correctness.

Reference problem summary:

```python
{preview}
```

You can inspect `/root/problem.py` directly.
If you need a starting point, `/root/starter_solution.py` contains a baseline
implementation, but you should still write `/root/generated_kernel.py`
yourself.
'''


def render_dockerfile(source: str) -> str:
    packages = ["torch==2.4.1", "numpy==1.26.4"]
    if "transformers" in source:
        packages.append("transformers==4.46.3")
    install_lines = " \\\n    ".join(packages)
    return f'''FROM python:3.10-slim

ARG http_proxy
ARG https_proxy
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG no_proxy
ARG NO_PROXY

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    http_proxy=${{http_proxy}} \
    https_proxy=${{https_proxy}} \
    HTTP_PROXY=${{HTTP_PROXY}} \
    HTTPS_PROXY=${{HTTPS_PROXY}} \
    no_proxy=${{no_proxy}} \
    NO_PROXY=${{NO_PROXY}}

WORKDIR /root

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --break-system-packages \
    {install_lines}

COPY problem.py /root/problem.py
COPY starter_solution.py /root/starter_solution.py

CMD ["sleep", "infinity"]
'''


def render_modelnew_source(source: str) -> str:
    updated, count = re.subn(r"class\s+Model\s*\(", "class ModelNew(", source, count=1)
    if count != 1:
        raise ValueError("Could not rewrite reference Model class to ModelNew")
    updated = re.sub(
        r"super\s*\(\s*Model\s*,\s*self\s*\)\s*\.\s*__init__\s*\(\s*\)",
        "super().__init__()",
        updated,
    )
    return updated.strip() + "\n"


def render_reference_solution_sh(modelnew_source: str) -> str:
    return f'''#!/bin/bash
set -euo pipefail

cat > /root/generated_kernel.py <<'PY'
{modelnew_source}PY
'''


def convert_problem(*, kernelbench_root: Path, level: int, problem_id: int, output_dir: Path):
    level_dir = kernelbench_root / "KernelBench" / f"level{level}"
    candidates = sorted(level_dir.glob(f"{problem_id}_*.py"))
    if not candidates:
        raise FileNotFoundError(f"No KernelBench problem found for level={level}, problem_id={problem_id}")
    if len(candidates) > 1:
        raise RuntimeError(f"Expected exactly one problem for level={level}, problem_id={problem_id}, found {len(candidates)}")

    problem_path = candidates[0]
    source = problem_path.read_text(encoding="utf-8")
    stem = problem_path.stem
    task_name = f"kb-l{level}-p{problem_id}-{task_slug(stem.split('_', 1)[1])}"
    task_dir = output_dir / task_name

    if task_dir.exists():
        shutil.rmtree(task_dir)

    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "solution").mkdir(parents=True)

    gpus = 1 if level >= 3 else 0
    modelnew_source = render_modelnew_source(source)

    (task_dir / "instruction.md").write_text(
        render_instruction(level=level, problem_id=problem_id, filename=problem_path.name, source=source),
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(TASK_TOML_TEMPLATE.format(gpus=gpus), encoding="utf-8")
    (task_dir / "environment" / "Dockerfile").write_text(render_dockerfile(source), encoding="utf-8")
    (task_dir / "environment" / "problem.py").write_text(source.strip() + "\n", encoding="utf-8")
    (task_dir / "environment" / "starter_solution.py").write_text(modelnew_source, encoding="utf-8")
    (task_dir / "tests" / "test.sh").write_text(TEST_SH, encoding="utf-8")
    (task_dir / "tests" / "verify.py").write_text(VERIFY_PY, encoding="utf-8")
    (task_dir / "tests" / "test_outputs.py").write_text(TEST_OUTPUTS_PY, encoding="utf-8")
    (task_dir / "solution" / "solve.sh").write_text(render_reference_solution_sh(modelnew_source), encoding="utf-8")

    for path in [task_dir / "tests" / "test.sh", task_dir / "solution" / "solve.sh"]:
        path.chmod(0o755)

    return task_dir


def iter_problem_ids(level_dir: Path) -> list[int]:
    problem_ids = set()
    for path in sorted(level_dir.glob("*.py")):
        match = re.match(r"(\d+)_", path.name)
        if match:
            problem_ids.add(int(match.group(1)))
    return sorted(problem_ids)


def convert_many(
    *,
    kernelbench_root: Path,
    levels: Iterable[int],
    output_dir: Path,
    skip_existing: bool,
) -> list[Path]:
    created = []
    for level in levels:
        level_dir = kernelbench_root / "KernelBench" / f"level{level}"
        for problem_id in iter_problem_ids(level_dir):
            candidates = sorted(level_dir.glob(f"{problem_id}_*.py"))
            if len(candidates) != 1:
                raise RuntimeError(
                    f"Expected exactly one problem for level={level}, problem_id={problem_id}, found {len(candidates)}"
                )
            problem_path = candidates[0]
            stem = problem_path.stem
            task_name = f"kb-l{level}-p{problem_id}-{task_slug(stem.split('_', 1)[1])}"
            task_dir = output_dir / task_name
            if skip_existing and task_dir.exists():
                print(f"SKIP {task_dir}")
                continue
            created.append(
                convert_problem(
                    kernelbench_root=kernelbench_root,
                    level=level,
                    problem_id=problem_id,
                    output_dir=output_dir,
                )
            )
    return created


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernelbench-root", type=Path, required=True)
    parser.add_argument("--level", type=int)
    parser.add_argument("--problem-id", type=int)
    parser.add_argument("--levels", type=int, nargs="+")
    parser.add_argument("--level-range", type=int, nargs=2, metavar=("START", "END"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.problem_id is not None and args.level is None:
        raise ValueError("--problem-id requires --level")

    if args.problem_id is not None:
        task_dir = convert_problem(
            kernelbench_root=args.kernelbench_root,
            level=args.level,
            problem_id=args.problem_id,
            output_dir=args.output_dir,
        )
        print(task_dir)
        return

    levels: list[int] = []
    if args.level is not None:
        levels.append(args.level)
    if args.levels:
        levels.extend(args.levels)
    if args.level_range:
        start, end = args.level_range
        levels.extend(range(start, end + 1))

    levels = sorted(set(levels))
    if not levels:
        raise ValueError("Specify either --level/--problem-id for one task or --levels/--level-range for batch conversion")

    created = convert_many(
        kernelbench_root=args.kernelbench_root,
        levels=levels,
        output_dir=args.output_dir,
        skip_existing=args.skip_existing,
    )
    for task_dir in created:
        print(task_dir)
    print(f"Created {len(created)} task(s)")


if __name__ == "__main__":
    main()
