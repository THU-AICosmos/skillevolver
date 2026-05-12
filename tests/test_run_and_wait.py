"""Tests for scripts/run_and_wait.py — pure logic tests (no Harbor subprocess)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys; sys.path.insert(0, str(Path(__file__).parent.parent / "skill-creator-v2" / "scripts"))
from run_and_wait import collect_and_preprocess, deploy_skill_to_task_variant


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

FIXTURE_JSONL = Path(__file__).parent / "fixtures" / "sample_trace.jsonl"


def _make_trial(
    tmp_path: Path, name: str, reward: int, jsonl_content: str = ""
) -> Path:
    """Create a fake Harbor trial directory.

    Parameters
    ----------
    tmp_path:
        Base temp directory (will be treated as the job dir).
    name:
        Trial subdirectory name (e.g. "task__aaaaaaa").
    reward:
        0 or 1 written to verifier/reward.txt.
    jsonl_content:
        Content to write to the .jsonl transcript.  If empty, the content of
        tests/fixtures/sample_trace.jsonl is used so that preprocess_trace and
        extract_metrics_from_jsonl can parse it without errors.
    """
    if not jsonl_content:
        jsonl_content = FIXTURE_JSONL.read_text(encoding="utf-8")

    trial = tmp_path / name
    (trial / "verifier").mkdir(parents=True)
    (trial / "verifier" / "reward.txt").write_text(str(reward), encoding="utf-8")

    sessions = trial / "agent" / "sessions" / "projects" / "-root"
    sessions.mkdir(parents=True)
    (sessions / "fake-session.jsonl").write_text(jsonl_content, encoding="utf-8")
    return trial


# ---------------------------------------------------------------------------
# 1. collect_and_preprocess writes <phase>-results.json with correct counts
# ---------------------------------------------------------------------------


class TestCollectAndPreprocessResultsJson:
    def test_results_json_written(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _make_trial(job_dir, "task__aaa1111", reward=1)
        _make_trial(job_dir, "task__bbb2222", reward=0)
        _make_trial(job_dir, "task__ccc3333", reward=0)

        collect_and_preprocess(job_dir, workspace, phase="exploration")

        results_path = workspace / "task" / "exploration-results.json"
        assert results_path.exists(), "results.json was not written"

    def test_correct_n_passed_n_failed(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _make_trial(job_dir, "task__aaa1111", reward=1)
        _make_trial(job_dir, "task__bbb2222", reward=0)
        _make_trial(job_dir, "task__ccc3333", reward=0)

        collect_and_preprocess(job_dir, workspace, phase="exploration")

        data = json.loads(
            (workspace / "task" / "exploration-results.json").read_text()
        )
        assert data["n_passed"] == 1
        assert data["n_failed"] == 2

    def test_n_attempts_is_sum(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _make_trial(job_dir, "task__p1aaaaa", reward=1)
        _make_trial(job_dir, "task__p2bbbbb", reward=1)
        _make_trial(job_dir, "task__f1ccccc", reward=0)

        collect_and_preprocess(job_dir, workspace, phase="skill-test")

        data = json.loads(
            (workspace / "task" / "skill-test-results.json").read_text()
        )
        assert data["n_attempts"] == 3

    def test_phase_field_matches(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _make_trial(job_dir, "task__x1aaaaa", reward=1)

        collect_and_preprocess(job_dir, workspace, phase="validation")

        data = json.loads(
            (workspace / "task" / "validation-results.json").read_text()
        )
        assert data["phase"] == "validation"


# ---------------------------------------------------------------------------
# 2. collect_and_preprocess writes per-trial trace files
# ---------------------------------------------------------------------------


class TestCollectAndPreprocessTraceFiles:
    def test_pass_trace_written(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _make_trial(job_dir, "task__p1aaaaa", reward=1)
        _make_trial(job_dir, "task__f1bbbbb", reward=0)

        collect_and_preprocess(job_dir, workspace, phase="exploration")

        traces_dir = workspace / "task" / "exploration-traces"
        assert traces_dir.exists()
        pass_files = list(traces_dir.glob("*-pass.md"))
        assert len(pass_files) >= 1

    def test_fail_trace_written(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _make_trial(job_dir, "task__p1aaaaa", reward=1)
        _make_trial(job_dir, "task__f1bbbbb", reward=0)

        collect_and_preprocess(job_dir, workspace, phase="exploration")

        traces_dir = workspace / "task" / "exploration-traces"
        fail_files = list(traces_dir.glob("*-fail.md"))
        assert len(fail_files) >= 1

    def test_trace_is_valid_markdown(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _make_trial(job_dir, "task__p1aaaaa", reward=1)
        _make_trial(job_dir, "task__f1bbbbb", reward=0)

        collect_and_preprocess(job_dir, workspace, phase="exploration")

        traces_dir = workspace / "task" / "exploration-traces"
        trace_files = list(traces_dir.glob("*.md"))
        assert len(trace_files) >= 1
        content = trace_files[0].read_text()
        assert "Agent Trace" in content or "## " in content or len(content) > 0


# ---------------------------------------------------------------------------
# 3. All-pass case: only pass traces, no fail traces
# ---------------------------------------------------------------------------


class TestAllPass:
    def test_pass_traces_present(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        for i in range(3):
            _make_trial(job_dir, f"task__{i}aaaaaa", reward=1)

        collect_and_preprocess(job_dir, workspace, phase="exploration")

        traces_dir = workspace / "task" / "exploration-traces"
        pass_files = list(traces_dir.glob("*-pass.md"))
        assert len(pass_files) == 3

    def test_no_fail_traces(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        for i in range(3):
            _make_trial(job_dir, f"task__{i}aaaaaa", reward=1)

        collect_and_preprocess(job_dir, workspace, phase="exploration")

        traces_dir = workspace / "task" / "exploration-traces"
        fail_files = list(traces_dir.glob("*-fail.md"))
        assert len(fail_files) == 0

    def test_results_json_counts(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        for i in range(4):
            _make_trial(job_dir, f"task__{i}aaaaaa", reward=1)

        collect_and_preprocess(job_dir, workspace, phase="exploration")

        data = json.loads(
            (workspace / "task" / "exploration-results.json").read_text()
        )
        assert data["n_passed"] == 4
        assert data["n_failed"] == 0


# ---------------------------------------------------------------------------
# 4. All-fail case: only fail traces, no pass traces
# ---------------------------------------------------------------------------


class TestAllFail:
    def test_fail_traces_present(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        for i in range(3):
            _make_trial(job_dir, f"task__{i}bbbbbb", reward=0)

        collect_and_preprocess(job_dir, workspace, phase="exploration")

        traces_dir = workspace / "task" / "exploration-traces"
        fail_files = list(traces_dir.glob("*-fail.md"))
        assert len(fail_files) == 3

    def test_no_pass_traces(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        for i in range(3):
            _make_trial(job_dir, f"task__{i}bbbbbb", reward=0)

        collect_and_preprocess(job_dir, workspace, phase="exploration")

        traces_dir = workspace / "task" / "exploration-traces"
        pass_files = list(traces_dir.glob("*-pass.md"))
        assert len(pass_files) == 0

    def test_results_json_counts(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        for i in range(2):
            _make_trial(job_dir, f"task__{i}bbbbbb", reward=0)

        collect_and_preprocess(job_dir, workspace, phase="skill-test")

        data = json.loads(
            (workspace / "task" / "skill-test-results.json").read_text()
        )
        assert data["n_passed"] == 0
        assert data["n_failed"] == 2


# ---------------------------------------------------------------------------
# 5. results.json must NOT contain Harbor paths
# ---------------------------------------------------------------------------


class TestResultsJsonNoHarborPaths:
    def test_no_jobs_path_in_results(self, tmp_path):
        job_dir = tmp_path / "jobs" / "some-task__abc1234"
        job_dir.mkdir(parents=True)
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _make_trial(job_dir, "trial__aaaaaa1", reward=1)
        _make_trial(job_dir, "trial__bbbbbbb", reward=0)

        collect_and_preprocess(job_dir, workspace, phase="exploration")

        content = (workspace / "task" / "exploration-results.json").read_text()
        assert "jobs/" not in content, "results.json should not contain Harbor job paths"

    def test_no_benchmarks_path_in_results(self, tmp_path):
        job_dir = tmp_path / "Benchmarks" / "skillsbench" / "jobs" / "task__xyz9999"
        job_dir.mkdir(parents=True)
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _make_trial(job_dir, "trial__aaaaaaa", reward=1)

        collect_and_preprocess(job_dir, workspace, phase="validation")

        content = (workspace / "task" / "validation-results.json").read_text()
        assert "Benchmarks" not in content, (
            "results.json should not contain Benchmarks path references"
        )


# ---------------------------------------------------------------------------
# 6. Phase name appears in filenames
# ---------------------------------------------------------------------------


class TestPhaseNamingConvention:
    @pytest.mark.parametrize("phase", ["exploration", "validation"])
    def test_filenames_use_phase_name(self, tmp_path, phase):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _make_trial(job_dir, "task__p1aaaaa", reward=1)
        _make_trial(job_dir, "task__f1bbbbb", reward=0)

        collect_and_preprocess(job_dir, workspace, phase=phase)

        task_dir = workspace / "task"
        assert (task_dir / f"{phase}-results.json").exists(), (
            f"Expected {phase}-results.json"
        )
        traces_dir = task_dir / f"{phase}-traces"
        assert traces_dir.exists(), f"Expected {phase}-traces directory"
        trace_files = list(traces_dir.glob("*.md"))
        assert len(trace_files) == 2, f"Expected 2 trace files, got {len(trace_files)}"


class TestValidationTraceIsolation:
    def test_validation_can_skip_trace_writes(self, tmp_path):
        job_dir = tmp_path / "job"
        job_dir.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        _make_trial(job_dir, "task__p1aaaaa", reward=1)
        _make_trial(job_dir, "task__f1bbbbb", reward=0)

        results = collect_and_preprocess(
            job_dir,
            workspace,
            phase="validation",
            write_traces=False,
        )

        assert not (workspace / "task" / "validation-traces").exists()
        assert len(results["trials"]) == 2
        assert all("trace_file" not in trial for trial in results["trials"])


# ---------------------------------------------------------------------------
# 7. deploy_skill_to_task_variant creates named subdirectory correctly
# ---------------------------------------------------------------------------


class TestDeploySkillToTaskVariant:
    def test_creates_named_subdirectory(self, tmp_path):
        # Create a skill_dir like iteration-1/skills/openpyxl-pivot-tables/
        skill_dir = tmp_path / "iteration-1" / "skills" / "openpyxl-pivot-tables"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Skill\nThis is the skill content.")

        task_env = tmp_path / "environment"
        task_env.mkdir()

        deploy_skill_to_task_variant(skill_dir, task_env)

        deployed = task_env / "skills" / "openpyxl-pivot-tables" / "SKILL.md"
        assert deployed.exists(), f"Expected SKILL.md at {deployed}"

    def test_skill_content_preserved(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        content = "# My Skill\nSome detailed content."
        (skill_dir / "SKILL.md").write_text(content)

        task_env = tmp_path / "environment"
        task_env.mkdir()

        deploy_skill_to_task_variant(skill_dir, task_env)

        deployed = task_env / "skills" / "my-skill" / "SKILL.md"
        assert deployed.read_text() == content

    def test_clears_existing_skills(self, tmp_path):
        # Pre-populate with an old skill
        old_skills = tmp_path / "environment" / "skills" / "old-skill"
        old_skills.mkdir(parents=True)
        (old_skills / "SKILL.md").write_text("# Old skill")

        skill_dir = tmp_path / "new-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# New skill")

        task_env = tmp_path / "environment"

        deploy_skill_to_task_variant(skill_dir, task_env)

        # Old skill must be gone
        assert not (task_env / "skills" / "old-skill").exists(), (
            "Old skill should have been cleared"
        )
        # New skill must be present
        assert (task_env / "skills" / "new-skill" / "SKILL.md").exists()

    def test_no_flat_skill_md_at_skills_root(self, tmp_path):
        """SKILL.md must NOT be placed directly under skills/ — must be in a subdirectory."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# My Skill")

        task_env = tmp_path / "environment"
        task_env.mkdir()

        deploy_skill_to_task_variant(skill_dir, task_env)

        flat_skill = task_env / "skills" / "SKILL.md"
        assert not flat_skill.exists(), (
            "SKILL.md must NOT be placed directly under skills/ root"
        )

    def test_multiple_files_in_skill_dir_are_copied(self, tmp_path):
        skill_dir = tmp_path / "rich-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Rich Skill")
        (skill_dir / "helpers.py").write_text("def helper(): pass")
        (skill_dir / "examples.md").write_text("# Examples")

        task_env = tmp_path / "environment"
        task_env.mkdir()

        deploy_skill_to_task_variant(skill_dir, task_env)

        dest = task_env / "skills" / "rich-skill"
        assert (dest / "SKILL.md").exists()
        assert (dest / "helpers.py").exists()
        assert (dest / "examples.md").exists()
