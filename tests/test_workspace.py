"""Regression tests for train/test split workspace context loading."""

from pathlib import Path

from agent.workspace import load_task_context


def _make_task(root: Path, task_name: str, instruction: str, dockerfile: str, data_name: str) -> Path:
    task_dir = root / task_name
    env_dir = task_dir / "environment"
    env_dir.mkdir(parents=True)
    (task_dir / "instruction.md").write_text(instruction, encoding="utf-8")
    (env_dir / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    (env_dir / data_name).write_text(f"payload for {data_name}", encoding="utf-8")
    return task_dir


def test_load_task_context_uses_explicit_tasks_root(tmp_path):
    task_name = "demo-task"
    original_root = tmp_path / "tasks"
    train_root = tmp_path / "tasks-train"

    _make_task(original_root, task_name, "original instruction", "FROM original", "original.txt")
    _make_task(train_root, task_name, "train instruction", "FROM train", "train.txt")

    instruction, dockerfile, data_files = load_task_context(
        task_name,
        tasks_root=train_root,
    )

    assert instruction == "train instruction"
    assert dockerfile == "FROM train"
    assert [path.name for path in data_files] == ["train.txt"]
