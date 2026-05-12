"""Tests for scripts/run_exploration.py — pure function tests only (no Harbor required)."""

from __future__ import annotations

from pathlib import Path

import pytest

import sys; sys.path.insert(0, str(Path(__file__).parent.parent / "skill-creator-v2" / "scripts"))
from run_exploration import collect_trial_results, pick_winner_loser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trial(tmp_path: Path, name: str, reward: int, transcript_content: str = "fake") -> Path:
    """Create a fake Harbor trial directory."""
    trial = tmp_path / name
    (trial / "verifier").mkdir(parents=True)
    (trial / "verifier" / "reward.txt").write_text(str(reward))
    sessions = trial / "agent" / "sessions" / "projects" / "-root"
    sessions.mkdir(parents=True)
    (sessions / "fake-session.jsonl").write_text(transcript_content)
    return trial


# ---------------------------------------------------------------------------
# collect_trial_results — counting tests
# ---------------------------------------------------------------------------


class TestCollectTrialResultsCounting:
    def test_counts_single_pass(self, tmp_path):
        _make_trial(tmp_path, "task__aaaaaaa", reward=1)
        results = collect_trial_results(tmp_path)
        assert results["n_passed"] == 1
        assert results["n_failed"] == 0

    def test_counts_single_fail(self, tmp_path):
        _make_trial(tmp_path, "task__bbbbbbb", reward=0)
        results = collect_trial_results(tmp_path)
        assert results["n_passed"] == 0
        assert results["n_failed"] == 1

    def test_counts_mixed_trials(self, tmp_path):
        _make_trial(tmp_path, "task__1111111", reward=1)
        _make_trial(tmp_path, "task__2222222", reward=0)
        _make_trial(tmp_path, "task__3333333", reward=1)
        _make_trial(tmp_path, "task__4444444", reward=0)
        _make_trial(tmp_path, "task__5555555", reward=0)
        results = collect_trial_results(tmp_path)
        assert results["n_passed"] == 2
        assert results["n_failed"] == 3

    def test_all_pass(self, tmp_path):
        for i in range(3):
            _make_trial(tmp_path, f"task__{i}aaaaaa", reward=1)
        results = collect_trial_results(tmp_path)
        assert results["n_passed"] == 3
        assert results["n_failed"] == 0

    def test_all_fail(self, tmp_path):
        for i in range(4):
            _make_trial(tmp_path, f"task__{i}bbbbbb", reward=0)
        results = collect_trial_results(tmp_path)
        assert results["n_passed"] == 0
        assert results["n_failed"] == 4

    def test_empty_job_dir(self, tmp_path):
        results = collect_trial_results(tmp_path)
        assert results["n_passed"] == 0
        assert results["n_failed"] == 0


# ---------------------------------------------------------------------------
# collect_trial_results — transcript path tests
# ---------------------------------------------------------------------------


class TestCollectTrialResultsTranscripts:
    def test_finds_jsonl_transcript_for_passing_trial(self, tmp_path):
        _make_trial(tmp_path, "task__aaaaaaa", reward=1, transcript_content='{"type":"assistant"}')
        results = collect_trial_results(tmp_path)
        assert len(results["passed_transcripts"]) == 1
        assert results["passed_transcripts"][0].suffix == ".jsonl"

    def test_finds_jsonl_transcript_for_failing_trial(self, tmp_path):
        _make_trial(tmp_path, "task__bbbbbbb", reward=0, transcript_content='{"type":"user"}')
        results = collect_trial_results(tmp_path)
        assert len(results["failed_transcripts"]) == 1
        assert results["failed_transcripts"][0].suffix == ".jsonl"

    def test_transcript_paths_are_absolute(self, tmp_path):
        _make_trial(tmp_path, "task__aaaaaaa", reward=1)
        _make_trial(tmp_path, "task__bbbbbbb", reward=0)
        results = collect_trial_results(tmp_path)
        for p in results["passed_transcripts"] + results["failed_transcripts"]:
            assert p.is_absolute(), f"Expected absolute path, got: {p}"

    def test_correct_number_of_transcripts_mixed(self, tmp_path):
        _make_trial(tmp_path, "task__1111111", reward=1)
        _make_trial(tmp_path, "task__2222222", reward=0)
        _make_trial(tmp_path, "task__3333333", reward=1)
        results = collect_trial_results(tmp_path)
        assert len(results["passed_transcripts"]) == 2
        assert len(results["failed_transcripts"]) == 1

    def test_transcript_content_preserved(self, tmp_path):
        _make_trial(tmp_path, "task__aaaaaaa", reward=1, transcript_content='{"type":"test"}')
        results = collect_trial_results(tmp_path)
        transcript_path = results["passed_transcripts"][0]
        assert transcript_path.read_text() == '{"type":"test"}'


# ---------------------------------------------------------------------------
# pick_winner_loser tests
# ---------------------------------------------------------------------------


class TestPickWinnerLoser:
    def _make_results(self, tmp_path: Path, n_pass: int, n_fail: int) -> dict:
        """Build a results dict with fake transcript paths."""
        passed = []
        failed = []
        for i in range(n_pass):
            trial = _make_trial(tmp_path, f"pass__{i}aaaaaa", reward=1)
            sessions = trial / "agent" / "sessions" / "projects" / "-root"
            passed.append((sessions / "fake-session.jsonl").resolve())
        for i in range(n_fail):
            trial = _make_trial(tmp_path, f"fail__{i}bbbbbb", reward=0)
            sessions = trial / "agent" / "sessions" / "projects" / "-root"
            failed.append((sessions / "fake-session.jsonl").resolve())
        return {
            "n_passed": n_pass,
            "n_failed": n_fail,
            "passed_transcripts": passed,
            "failed_transcripts": failed,
        }

    def test_returns_tuple_when_both_exist(self, tmp_path):
        results = self._make_results(tmp_path, n_pass=2, n_fail=2)
        pair = pick_winner_loser(results)
        assert pair is not None
        assert len(pair) == 2

    def test_winner_comes_from_passed(self, tmp_path):
        results = self._make_results(tmp_path, n_pass=3, n_fail=3)
        pair = pick_winner_loser(results)
        assert pair is not None
        winner, _ = pair
        assert winner in results["passed_transcripts"]

    def test_loser_comes_from_failed(self, tmp_path):
        results = self._make_results(tmp_path, n_pass=3, n_fail=3)
        pair = pick_winner_loser(results)
        assert pair is not None
        _, loser = pair
        assert loser in results["failed_transcripts"]

    def test_returns_none_when_all_pass(self, tmp_path):
        results = self._make_results(tmp_path, n_pass=4, n_fail=0)
        assert pick_winner_loser(results) is None

    def test_returns_none_when_all_fail(self, tmp_path):
        results = self._make_results(tmp_path, n_pass=0, n_fail=4)
        assert pick_winner_loser(results) is None

    def test_returns_none_when_both_empty(self):
        results = {
            "n_passed": 0,
            "n_failed": 0,
            "passed_transcripts": [],
            "failed_transcripts": [],
        }
        assert pick_winner_loser(results) is None

    def test_returned_paths_have_jsonl_suffix(self, tmp_path):
        results = self._make_results(tmp_path, n_pass=2, n_fail=2)
        pair = pick_winner_loser(results)
        assert pair is not None
        winner, loser = pair
        assert winner.suffix == ".jsonl"
        assert loser.suffix == ".jsonl"

    def test_single_pass_single_fail(self, tmp_path):
        results = self._make_results(tmp_path, n_pass=1, n_fail=1)
        pair = pick_winner_loser(results)
        assert pair is not None
        winner, loser = pair
        assert winner == results["passed_transcripts"][0]
        assert loser == results["failed_transcripts"][0]

    def test_randomness_selects_from_pool(self, tmp_path):
        """With multiple candidates, repeated calls should eventually pick different ones."""
        results = self._make_results(tmp_path, n_pass=5, n_fail=5)
        winners = set()
        for _ in range(30):
            pair = pick_winner_loser(results)
            assert pair is not None
            winners.add(pair[0])
        # With 5 winners and 30 draws, probability of always picking the same one is (1/5)^29
        assert len(winners) > 1, "Expected random selection from pool, got same winner every time"
