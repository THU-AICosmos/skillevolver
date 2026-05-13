"""Pytest assertions for the Logistics PDDL train variant.

Same overall shape as the validation task (file-existence, plan-format,
plan-validity), but reorganised as module-level fixtures instead of a class
hierarchy and using different helper names.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List

import pytest
from unified_planning.io import PDDLReader
from unified_planning.shortcuts import PlanValidator

MANIFEST = Path("/app/problem.json")
APP_ROOT = Path("/app")


@dataclass(frozen=True)
class PlannedTask:
    tag: str
    domain: Path
    problem: Path
    plan_file: Path


def _resolve_manifest() -> List[PlannedTask]:
    raw = json.loads(MANIFEST.read_text())
    out = []
    for entry in raw:
        out.append(
            PlannedTask(
                tag=entry["id"],
                domain=APP_ROOT / entry["domain"],
                problem=APP_ROOT / entry["problem"],
                plan_file=Path(entry["plan_output"]),
            )
        )
    return out


@pytest.fixture(scope="module")
def planned_tasks() -> List[PlannedTask]:
    return _resolve_manifest()


def _iter_action_lines(plan_file: Path) -> Iterator[str]:
    for raw in plan_file.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        yield line


def _assert_plan_syntax(plan_file: Path) -> None:
    saw_any = False
    for line in _iter_action_lines(plan_file):
        saw_any = True
        if "(" not in line or ")" not in line:
            raise AssertionError(f"Action line missing parentheses: {line!r} in {plan_file}")
        if line.count("(") != 1 or line.count(")") != 1:
            raise AssertionError(f"Multiple actions on one line: {line!r} in {plan_file}")
    if not saw_any:
        raise AssertionError(f"Plan file is empty: {plan_file}")


def _validate_against_pddl(task: PlannedTask) -> bool:
    reader = PDDLReader()
    parsed = reader.parse_problem(str(task.domain), str(task.problem))
    submitted = reader.parse_plan(parsed, str(task.plan_file))
    with PlanValidator(problem_kind=parsed.kind, plan_kind=submitted.kind) as v:
        report = v.validate(parsed, submitted)
        print(f"  validator report for {task.tag}: {report}")
        return bool(report)


def test_each_plan_file_present(planned_tasks: List[PlannedTask]) -> None:
    """Plan output files must exist on disk after solve.sh."""
    missing = [t.plan_file for t in planned_tasks if not t.plan_file.exists()]
    assert not missing, f"Missing plan output(s): {missing}"


@pytest.mark.parametrize("rtol,atol", [(1e-5, 1e-6)])
def test_each_plan_validates(rtol: float, atol: float, planned_tasks: List[PlannedTask]) -> None:
    """Each generated plan must parse with PDDLReader and pass PlanValidator."""
    for task in planned_tasks:
        _assert_plan_syntax(task.plan_file)
        print(task.domain, task.problem, task.plan_file)
        ok = _validate_against_pddl(task)
        assert ok, f"Plan validation failed for {task.tag}"
