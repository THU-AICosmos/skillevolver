"""Tests for scripts/preprocess_trace.py"""

import json
import os
import tempfile
from pathlib import Path

import pytest

import sys; sys.path.insert(0, str(Path(__file__).parent.parent / "skill-creator-v2" / "scripts"))
from preprocess_trace import extract_metrics_from_jsonl, preprocess_trace

FIXTURE = Path(__file__).parent / "fixtures" / "sample_trace.jsonl"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_markdown(reward: int = 1) -> str:
    return preprocess_trace(str(FIXTURE), reward=reward)


# ---------------------------------------------------------------------------
# Header / structure tests
# ---------------------------------------------------------------------------

class TestHeader:
    def test_reward_1_header(self):
        md = get_markdown(reward=1)
        assert md.startswith("# Agent Trace (reward: 1)")

    def test_reward_0_header(self):
        md = get_markdown(reward=0)
        assert md.startswith("# Agent Trace (reward: 0)")

    def test_has_turn_headings(self):
        md = get_markdown()
        assert "## Turn 1" in md

    def test_multiple_turn_headings(self):
        md = get_markdown()
        # The fixture has 4 distinct assistant messages (msg_001..msg_004)
        # which should produce at least 2 turns
        turn_count = md.count("## Turn ")
        assert turn_count >= 2, f"Expected >=2 turns, got {turn_count}"


# ---------------------------------------------------------------------------
# Stripping tests
# ---------------------------------------------------------------------------

class TestStripping:
    def test_strips_queue_operation(self):
        md = get_markdown()
        assert "queue-operation" not in md
        assert "enqueue" not in md

    def test_strips_last_prompt(self):
        md = get_markdown()
        assert "last-prompt" not in md
        assert "lastPrompt" not in md

    def test_strips_system_messages(self):
        md = get_markdown()
        assert "System message" not in md
        assert "compactMetadata" not in md

    def test_strips_uuids(self):
        md = get_markdown()
        # UUIDs from the fixture (top-level fields) should not appear
        assert "aaa00001-0000-0000-0000-000000000001" not in md
        assert "83f86a96-55e3-4066-90f4-3263cf513ddb" not in md

    def test_strips_token_usage(self):
        md = get_markdown()
        assert "input_tokens" not in md
        assert "cache_creation_input_tokens" not in md
        assert "cache_read_input_tokens" not in md

    def test_strips_signatures(self):
        md = get_markdown()
        assert "FAKESIGNATURE123==" not in md
        assert "FAKESIG456==" not in md

    def test_strips_session_id_field(self):
        md = get_markdown()
        assert "sessionId" not in md

    def test_strips_is_sidechain(self):
        md = get_markdown()
        assert "isSidechain" not in md

    def test_strips_permission_mode(self):
        md = get_markdown()
        assert "permissionMode" not in md

    def test_strips_version(self):
        md = get_markdown()
        assert '"2.1.72"' not in md

    def test_strips_git_branch(self):
        md = get_markdown()
        assert "gitBranch" not in md


# ---------------------------------------------------------------------------
# Preservation tests
# ---------------------------------------------------------------------------

class TestPreservation:
    def test_preserves_thinking_text(self):
        md = get_markdown()
        assert "Let me start by reading the data file" in md
        assert "I can see the CSV has 3 columns" in md

    def test_preserves_thinking_heading(self):
        md = get_markdown()
        assert "### Thinking" in md

    def test_preserves_tool_call_read(self):
        md = get_markdown()
        assert "### Tool Call: Read" in md
        assert "file_path: /root/data.csv" in md

    def test_preserves_tool_call_bash(self):
        md = get_markdown()
        assert "### Tool Call: Bash" in md
        assert "pd.read_csv" in md

    def test_preserves_tool_call_write(self):
        md = get_markdown()
        assert "### Tool Call: Write" in md
        assert "file_path: /root/summary.txt" in md

    def test_preserves_tool_result_stdout(self):
        md = get_markdown()
        assert "col1,col2,col3" in md

    def test_preserves_error_output(self):
        md = get_markdown()
        # stderr from the failed bash command
        assert "ModuleNotFoundError" in md or "No module named 'pandas'" in md

    def test_preserves_written_file_content(self):
        md = get_markdown()
        # The Write tool result should include file content
        assert "Total rows: 2" in md

    def test_preserves_text_response(self):
        md = get_markdown()
        assert "I have read the CSV and written a summary" in md

    def test_preserves_response_heading(self):
        md = get_markdown()
        assert "### Response" in md

    def test_preserves_tool_result_heading(self):
        md = get_markdown()
        assert "### Tool Result" in md


# ---------------------------------------------------------------------------
# Sanitization tests
# ---------------------------------------------------------------------------

class TestSanitization:
    def test_sanitizes_harbor_paths(self):
        md = get_markdown()
        # The fixture has a tool_result with a Benchmarks/skillsbench/jobs/ path
        assert "Benchmarks/skillsbench/jobs/" not in md
        assert "[harbor-path]" in md


# ---------------------------------------------------------------------------
# File output test
# ---------------------------------------------------------------------------

class TestFileOutput:
    def test_writes_to_file(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            out_path = f.name
        try:
            result = preprocess_trace(str(FIXTURE), reward=1, output_path=out_path)
            content = Path(out_path).read_text(encoding="utf-8")
            assert content == result
            assert content.startswith("# Agent Trace (reward: 1)")
        finally:
            os.unlink(out_path)

    def test_returns_string_even_without_output_path(self):
        result = preprocess_trace(str(FIXTURE), reward=0)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# extract_metrics_from_jsonl tests
# ---------------------------------------------------------------------------

class TestExtractMetrics:
    def get_metrics(self):
        return extract_metrics_from_jsonl(str(FIXTURE))

    def test_returns_dict(self):
        m = self.get_metrics()
        assert isinstance(m, dict)

    def test_has_required_keys(self):
        m = self.get_metrics()
        assert "input_tokens" in m
        assert "output_tokens" in m
        assert "total_tokens" in m
        assert "n_turns" in m
        assert "duration_seconds" in m

    def test_n_turns_positive(self):
        m = self.get_metrics()
        assert m["n_turns"] > 0, f"Expected n_turns > 0, got {m['n_turns']}"

    def test_n_turns_matches_assistant_messages(self):
        # The fixture has 4 unique assistant message IDs (msg_001..msg_004)
        m = self.get_metrics()
        assert m["n_turns"] == 4, f"Expected 4 turns, got {m['n_turns']}"

    def test_input_tokens_positive(self):
        m = self.get_metrics()
        assert m["input_tokens"] > 0

    def test_output_tokens_positive(self):
        m = self.get_metrics()
        assert m["output_tokens"] > 0

    def test_total_tokens_equals_sum(self):
        m = self.get_metrics()
        expected = m["input_tokens"] + m["output_tokens"] + m["cache_read_tokens"] + m["cache_creation_tokens"]
        assert m["total_tokens"] == expected

    def test_duration_seconds_non_negative(self):
        m = self.get_metrics()
        assert m["duration_seconds"] >= 0

    def test_input_tokens_excludes_cache(self):
        # From fixture: msg_001 last chunk has input=10, msg_002: 5, msg_003: 8, msg_004: 6
        # Total input (uncached) = 10 + 5 + 8 + 6 = 29
        m = self.get_metrics()
        assert m["input_tokens"] == 29, f"Expected 29 input tokens, got {m['input_tokens']}"

    def test_cache_read_tokens(self):
        # msg_001: 200, msg_002: 700, msg_003: 900, msg_004: 1100 = 2900
        m = self.get_metrics()
        assert m["cache_read_tokens"] == 2900, f"Expected 2900, got {m['cache_read_tokens']}"

    def test_cache_creation_tokens(self):
        # msg_001: 500, msg_002: 150, msg_003: 200, msg_004: 100 = 950
        m = self.get_metrics()
        assert m["cache_creation_tokens"] == 950, f"Expected 950, got {m['cache_creation_tokens']}"

    def test_output_tokens_sum(self):
        # msg_001: 85, msg_002: 200, msg_003: 120, msg_004: 55 = 460
        m = self.get_metrics()
        assert m["output_tokens"] == 460, f"Expected 460 output tokens, got {m['output_tokens']}"
