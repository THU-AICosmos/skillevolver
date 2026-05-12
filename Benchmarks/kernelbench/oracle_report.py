#!/usr/bin/env python3
"""Run an oracle-style correctness/speed smoke test for converted Harbor tasks."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path


WORKER_SOURCE = r"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import time
import traceback
from pathlib import Path

import tomllib
import torch


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


def benchmark(model, base_inputs, device: str, warmup: int, repeats: int) -> float:
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


def main():
    task_dir = Path(sys.argv[1]).resolve()
    warmup = int(sys.argv[2])
    repeats = int(sys.argv[3])

    task_config = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
    wants_gpu = int(task_config["environment"].get("gpus", 0)) > 0
    device = "cuda" if wants_gpu and torch.cuda.is_available() else "cpu"

    problem_path = task_dir / "environment" / "problem.py"
    starter_path = task_dir / "environment" / "starter_solution.py"

    payload = {
        "task": task_dir.name,
        "device": device,
        "correctness": 0,
        "reward": 0.0,
        "speedup": 0.0,
        "status": "failed",
    }

    try:
        ref_mod = load_module(problem_path, "reference_problem")
        solution_mod = load_module(starter_path, "candidate_solution")
        init_inputs = clone_value(ref_mod.get_init_inputs()) if hasattr(ref_mod, "get_init_inputs") else []
        eval_inputs = clone_value(ref_mod.get_inputs()) if hasattr(ref_mod, "get_inputs") else []

        ref_model = ref_mod.Model(*init_inputs).eval().to(device)
        candidate_model = solution_mod.ModelNew(*init_inputs).eval().to(device)
        candidate_model.load_state_dict(ref_model.state_dict(), strict=False)

        expected = forward_once(ref_model, eval_inputs, device)
        actual = forward_once(candidate_model, eval_inputs, device)
        assert_close_structures(actual, expected)

        reference_time = benchmark(ref_model, eval_inputs, device, warmup=warmup, repeats=repeats)
        candidate_time = benchmark(candidate_model, eval_inputs, device, warmup=warmup, repeats=repeats)
        speedup = max(reference_time / max(candidate_time, 1e-9), 0.0)

        payload.update(
            {
                "correctness": 1,
                "reward": float(speedup),
                "speedup": float(speedup),
                "status": "passed",
                "reference_time_sec": reference_time,
                "candidate_time_sec": candidate_time,
            }
        )
    except Exception as exc:
        payload.update(
            {
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    finally:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    print(json.dumps(payload))


if __name__ == "__main__":
    main()
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-dir", type=Path, nargs="+", required=True)
    parser.add_argument("--levels", type=int, nargs="+", default=[3, 4])
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--timeout-sec", type=int, default=1200)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    return parser.parse_args()


def iter_task_dirs(task_roots: list[Path], levels: set[int]) -> list[Path]:
    task_dirs: list[Path] = []
    for root in task_roots:
        for path in sorted(root.iterdir()):
            if not path.is_dir():
                continue
            if not path.name.startswith("kb-l"):
                continue
            try:
                level = int(path.name.split("-")[1][1:])
            except Exception:
                continue
            if level in levels:
                task_dirs.append(path.resolve())
    return sorted(task_dirs, key=lambda p: p.name)


def run_single_task(task_dir: Path, *, warmup: int, repeats: int, timeout_sec: int) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
        handle.write(textwrap.dedent(WORKER_SOURCE))
        worker_path = Path(handle.name)

    try:
        proc = subprocess.run(
            [sys.executable, str(worker_path), str(task_dir), str(warmup), str(repeats)],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return {
            "task": task_dir.name,
            "status": "timeout",
            "correctness": 0,
            "reward": 0.0,
            "speedup": 0.0,
            "error_type": "TimeoutExpired",
            "error_message": f"Timed out after {timeout_sec} seconds",
        }
    finally:
        worker_path.unlink(missing_ok=True)

    if proc.returncode != 0:
        return {
            "task": task_dir.name,
            "status": "worker-error",
            "correctness": 0,
            "reward": 0.0,
            "speedup": 0.0,
            "error_type": "WorkerProcessError",
            "error_message": proc.stderr.strip() or proc.stdout.strip(),
        }

    return json.loads(proc.stdout)


def write_markdown(results: list[dict], output_md: Path) -> None:
    passed = [r for r in results if r.get("correctness") == 1]
    failed = [r for r in results if r.get("correctness") != 1]

    lines = [
        "# KernelBench Harbor Oracle Report",
        "",
        f"- Tested tasks: {len(results)}",
        f"- Passed (`correctness=1`): {len(passed)}",
        f"- Failed: {len(failed)}",
        "",
        "## Passed",
        "",
    ]

    if passed:
        for row in passed:
            lines.append(
                f"- `{row['task']}`: reward={row['reward']:.6f}, speedup={row['speedup']:.6f}, device={row.get('device', 'n/a')}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Failed", ""])
    if failed:
        for row in failed:
            lines.append(
                f"- `{row['task']}`: {row.get('error_type', row.get('status', 'failed'))}: {row.get('error_message', 'unknown error')}"
            )
    else:
        lines.append("- None")

    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    task_dirs = iter_task_dirs(args.tasks_dir, set(args.levels))
    results = []

    started = time.time()
    for task_dir in task_dirs:
        results.append(
            run_single_task(
                task_dir,
                warmup=args.warmup,
                repeats=args.repeats,
                timeout_sec=args.timeout_sec,
            )
        )

    summary = {
        "generated_at": int(started),
        "tasks_tested": len(results),
        "passed": sum(1 for row in results if row.get("correctness") == 1),
        "failed": sum(1 for row in results if row.get("correctness") != 1),
        "results": results,
    }
    args.output_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_markdown(results, args.output_md)


if __name__ == "__main__":
    main()
