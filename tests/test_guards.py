"""Tests for the can_use_tool path guard."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from agent.guards import check_path_access


class TestCheckPathAccess:
    """Test the synchronous path-checking logic."""

    def setup_method(self):
        self.allowed_prefixes = [
            "/home/user/evolved-skills/task1/20260324/",
            "/home/user/workplace/self-evolving-skills/skill-creator-v2/",
            "/home/user/workplace/self-evolving-skills/agent/",
        ]

    def test_allows_workspace_file(self):
        result = check_path_access(
            "/home/user/evolved-skills/task1/20260324/iteration-1/skills/foo/SKILL.md",
            self.allowed_prefixes,
        )
        assert result is None  # None means allowed

    def test_blocks_test_outputs(self):
        result = check_path_access(
            "/home/user/Benchmarks/skillsbench/tasks/sales-pivot-analysis/test_outputs.py",
            self.allowed_prefixes,
        )
        assert result is not None
        assert "blocked" in result.lower()

    def test_blocks_solution_dir(self):
        result = check_path_access(
            "/home/user/Benchmarks/skillsbench/tasks/earthquake/solution/solution.py",
            self.allowed_prefixes,
        )
        assert result is not None

    def test_blocks_solve_sh(self):
        result = check_path_access(
            "/home/user/Benchmarks/skillsbench/tasks/foo/solve.sh",
            self.allowed_prefixes,
        )
        assert result is not None

    def test_blocks_expected_output(self):
        result = check_path_access(
            "/home/user/Benchmarks/skillsbench/tasks/foo/expected_output.json",
            self.allowed_prefixes,
        )
        assert result is not None

    def test_blocks_curated_skills(self):
        result = check_path_access(
            "/home/user/Benchmarks/skillsbench/tasks/foo/environment/skills/curated/SKILL.md",
            self.allowed_prefixes,
        )
        assert result is not None

    def test_blocks_tasks_dir_directly(self):
        result = check_path_access(
            "/home/user/Benchmarks/skillsbench/tasks/sales-pivot-analysis/instruction.md",
            self.allowed_prefixes,
        )
        assert result is not None

    def test_allows_skill_creator_dir(self):
        result = check_path_access(
            "/home/user/workplace/self-evolving-skills/skill-creator-v2/SKILL.md",
            self.allowed_prefixes,
        )
        assert result is None

    def test_allows_scripts_dir(self):
        result = check_path_access(
            "/home/user/workplace/self-evolving-skills/skill-creator-v2/scripts/run_and_wait.py",
            self.allowed_prefixes,
        )
        assert result is None

    def test_allows_agent_dir(self):
        result = check_path_access(
            "/home/user/workplace/self-evolving-skills/agent/config.py",
            self.allowed_prefixes,
        )
        assert result is None


class TestCheckBashCommand:
    """Test Bash command string checking."""

    def test_blocks_bash_with_tasks_path(self):
        from agent.guards import check_bash_command
        result = check_bash_command(
            "cat Benchmarks/skillsbench/tasks/foo/test_outputs.py"
        )
        assert result is not None

    def test_allows_run_and_wait(self):
        from agent.guards import check_bash_command
        result = check_bash_command(
            "python scripts/run_and_wait.py --task foo --phase exploration"
        )
        assert result is None

    def test_blocks_solve_sh_reference(self):
        from agent.guards import check_bash_command
        result = check_bash_command("cat solve.sh")
        assert result is not None

    def test_allows_normal_commands(self):
        from agent.guards import check_bash_command
        result = check_bash_command("ls -la iteration-1/skills/")
        assert result is None


def test_set_allowed_prefixes_accepts_multiple_paths(tmp_path):
    from agent import guards
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    guards.set_allowed_prefixes([a, b])
    assert guards.is_path_allowed(str(a / "file.txt"))
    assert guards.is_path_allowed(str(b / "x.json"))
    assert not guards.is_path_allowed(str(tmp_path / "c" / "x"))

def test_set_allowed_prefixes_narrower_than_configure(tmp_path):
    from agent import guards
    workspace = tmp_path / "ws"
    narrow = workspace / "subdir"
    narrow.mkdir(parents=True)
    guards.set_allowed_prefixes([narrow])
    assert not guards.is_path_allowed(str(workspace / "other.txt"))
    assert guards.is_path_allowed(str(narrow / "ok.txt"))
