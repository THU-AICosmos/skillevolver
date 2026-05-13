"""
Use this file to define pytest tests that verify the outputs of the task.

This file will be copied to /tests/test_outputs.py and run by the /tests/test.sh file
from the working directory.
"""

import json
import os
import pickle

import pytest
from unified_planning.io import PDDLReader
from unified_planning.shortcuts import OneshotPlanner

MANIFEST_PATH = "/app/problem.json"

# directory conventions inside container
DATA_DIR = "/app/marketplace"


def cross_check_plan(dom_pddl, prb_pddl, txt_out):
    rdr = PDDLReader()

    # parse domain+problem
    parsed = rdr.parse_problem(dom_pddl, prb_pddl)

    # --- Solve with reference engine ---
    with OneshotPlanner(name="pyperplan") as engine:
        outcome = engine.solve(parsed)

    if outcome.plan is None:
        print("Reference engine produced no plan")
        return False

    ref_plan = outcome.plan

    # parse candidate plan from pickle (same engine output, serialized by solve.sh)
    pkl_path = txt_out.replace(".txt", ".pkl")
    with open(pkl_path, "rb") as fh:
        cand_plan = pickle.load(fh)

    ref_steps = [str(a) for a in ref_plan.actions]
    cand_steps = [str(a) for a in cand_plan.actions]
    if ref_steps == cand_steps:
        return True
    else:
        print(f"Mismatch: ref={ref_steps}, cand={cand_steps}")
        return False


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------


def read_manifest():
    with open(MANIFEST_PATH) as fh:
        return json.load(fh)


def to_path(name):
    return os.path.join(name)


def lint_plan_text(txt_out):
    with open(txt_out) as fh:
        rows = [r.strip() for r in fh.readlines()]

    for idx, r in enumerate(rows):
        assert r, f"Empty line in plan at line {idx}"

    for r in rows:
        assert "(" in r and ")" in r, f"Invalid action syntax: {r}"

        assert r.count("(") == 1 and r.count(")") == 1, f"Multiple actions in one line: {r}"


# ---------------------------------------------------------
# File existence & basic validity
# ---------------------------------------------------------


class TestPlanArtifactsPresent:
    """Check all required output and answer files exist."""

    def test_all_plan_files_exist(self):
        entries = read_manifest()
        for e in entries:
            out = to_path(e["plan_output"])
            assert os.path.exists(out), f"Missing output file: {out}"


# ---------------------------------------------------------
# Correctness
# ---------------------------------------------------------


class TestPlanMatchesReference:
    """Check candidate plan matches the reference solver output."""

    @pytest.mark.parametrize("rtol, atol", [(1e-5, 1e-6)])
    def test_allclose(self, rtol, atol):
        entries = read_manifest()
        for e in entries:
            lint_plan_text(e["plan_output"])
            print(e["domain"], e["problem"], e["plan_output"])
            ok = cross_check_plan(e["domain"], e["problem"], e["plan_output"])
            assert ok, f"Plan error in task {e['id']}"
