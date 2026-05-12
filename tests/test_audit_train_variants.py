"""Tests for the train-variant similarity audit."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from audit_train_variants import audit_task_pair


def _write_task(root: Path, task_name: str, *, instruction: str, solve: str, test: str) -> Path:
    task_dir = root / task_name
    (task_dir / "environment" / "skills").mkdir(parents=True)
    (task_dir / "solution").mkdir(parents=True)
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "instruction.md").write_text(instruction, encoding="utf-8")
    (task_dir / "solution" / "solve.sh").write_text(solve, encoding="utf-8")
    (task_dir / "tests" / "test_outputs.py").write_text(test, encoding="utf-8")
    (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.11", encoding="utf-8")
    return task_dir


def test_audit_flags_identical_environment_files(tmp_path):
    original = _write_task(
        tmp_path / "tasks",
        "demo",
        instruction="original instruction",
        solve="echo original",
        test="assert True",
    )
    train = _write_task(
        tmp_path / "tasks-train",
        "demo",
        instruction="different instruction",
        solve="echo train",
        test="assert True",
    )

    (original / "environment" / "data.csv").write_text("same-bytes", encoding="utf-8")
    (train / "environment" / "data.csv").write_text("same-bytes", encoding="utf-8")

    report = audit_task_pair(original, train)

    assert report["risk_level"] == "high"
    assert report["identical_environment_files"] == ["data.csv"]


def test_audit_ignores_skills_directory_when_comparing_environment(tmp_path):
    original = _write_task(
        tmp_path / "tasks",
        "demo",
        instruction="instruction one",
        solve="echo one",
        test="assert True",
    )
    train = _write_task(
        tmp_path / "tasks-train",
        "demo",
        instruction="instruction two",
        solve="echo two",
        test="assert False",
    )

    (original / "environment" / "skills" / "helper.txt").write_text("same", encoding="utf-8")
    (train / "environment" / "skills" / "helper.txt").write_text("same", encoding="utf-8")

    report = audit_task_pair(original, train)

    assert report["identical_environment_files"] == []
    assert report["risk_level"] in {"low", "medium"}
