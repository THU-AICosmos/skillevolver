"""
preprocess_trace.py — Convert Harbor .jsonl session logs to clean markdown.

Usage:
    python -m scripts.preprocess_trace --input PATH --output PATH --reward 0|1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

# Fields to strip from top-level event objects
_TOP_LEVEL_STRIP = {
    "uuid", "parentUuid", "sessionId", "isSidechain", "userType",
    "timestamp", "version", "gitBranch", "permissionMode",
    "sourceToolAssistantUUID", "isMeta", "isVisibleInTranscriptOnly",
    "isCompactSummary", "slug",
}

# Types of events to skip entirely
_SKIP_TYPES = {"queue-operation", "last-prompt", "system"}

# Regex to sanitize Harbor job paths (host-side)
_HARBOR_PATH_RE = re.compile(
    r"(?:[^\s\"']*/)?" r"Benchmarks/skillsbench/jobs/[^\s\"']*"
)

# Regex to sanitize session file paths inside Harbor containers
# e.g. /logs/agent/sessions/projects/-root/<uuid>.jsonl
_SESSION_PATH_RE = re.compile(
    r"/logs/agent/sessions/[^\s\"']*"
)


def _sanitize(text: str) -> str:
    """Replace Harbor job paths and session paths with placeholders."""
    text = _HARBOR_PATH_RE.sub("[harbor-path]", text)
    text = _SESSION_PATH_RE.sub("[session-path]", text)
    return text


def _coerce_text(value) -> str:
    """Normalize transcript payloads into sanitized plain text."""
    if isinstance(value, str):
        return _sanitize(value)
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(_sanitize(item.get("text", "")))
                elif "text" in item:
                    parts.append(_sanitize(str(item["text"])))
                else:
                    parts.append(_sanitize(json.dumps(item, ensure_ascii=False)))
            else:
                parts.append(_sanitize(str(item)))
        return "\n".join(part for part in parts if part)
    return _sanitize(str(value))


def _render_tool_input(input_dict: dict) -> str:
    """Render tool input fields as key: value lines."""
    lines = []
    for k, v in input_dict.items():
        if isinstance(v, str):
            lines.append(f"{k}: {v}")
        else:
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    return "\n".join(lines)


def _render_tool_result(content) -> str:
    """Render tool_result content block(s) as plain text."""
    return _coerce_text(content)


def _render_tooluse_result(tur) -> str:
    """Render a toolUseResult (dict or str) as text."""
    if isinstance(tur, str):
        return _sanitize(tur)
    if not isinstance(tur, dict):
        return _sanitize(str(tur))
    tur_type = tur.get("type", "")

    # Bash / command execution result
    if "stdout" in tur or "stderr" in tur:
        parts = []
        stdout = tur.get("stdout", "")
        stderr = tur.get("stderr", "")
        if stdout:
            parts.append(_sanitize(stdout))
        if stderr:
            parts.append(f"[stderr]\n{_sanitize(stderr)}")
        return "\n".join(parts) if parts else "(no output)"

    # File write / create result — include file content
    if tur_type in ("create", "edit") or "content" in tur:
        file_path = tur.get("filePath", "")
        content = tur.get("content", "")
        if content:
            sanitized_path = _sanitize(file_path)
            return f"File written: {sanitized_path}\n\n{_coerce_text(content)}"
        if file_path:
            return f"File operation: {_sanitize(file_path)}"

    # Structured patch (Edit tool)
    if "structuredPatch" in tur:
        file_path = _sanitize(tur.get("filePath", ""))
        old_string = tur.get("oldString", "")
        new_string = tur.get("newString", "")
        parts = [f"Edit applied to: {file_path}"]
        if old_string:
            parts.append(f"old:\n{old_string}")
        if new_string:
            parts.append(f"new:\n{new_string}")
        return "\n".join(parts)

    # PDF file result — skip binary, just note the file
    if tur_type == "pdf":
        fp = _sanitize(tur.get("file", {}).get("filePath", ""))
        return f"[PDF file: {fp}]"

    # Generic fallback — avoid dumping binary base64 blobs
    safe = {k: v for k, v in tur.items() if k not in ("base64", "data", "file")}
    return _sanitize(json.dumps(safe, ensure_ascii=False, indent=2))


class _Turn:
    """Represents a single assistant turn with its associated tool calls/results."""

    def __init__(self, index: int):
        self.index = index
        self.sections: list[tuple[str, str]] = []  # (heading, body)

    def add(self, heading: str, body: str):
        if body and body.strip():
            self.sections.append((heading, body.strip()))

    def render(self) -> str:
        if not self.sections:
            return ""
        if self.index == 0:
            lines = ["## Task Prompt"]
        else:
            lines = [f"## Turn {self.index}"]
        for heading, body in self.sections:
            # For Turn 0, the single "Task Prompt" section body goes directly
            # under the heading without a sub-heading
            if self.index == 0 and heading == "Task Prompt":
                lines.append(body)
            else:
                lines.append(f"\n### {heading}")
                lines.append(body)
        return "\n".join(lines)


def preprocess_trace(
    input_path: str,
    reward: int,
    output_path: Optional[str] = None,
) -> str:
    """
    Convert a Harbor .jsonl session log to a clean markdown string.

    Parameters
    ----------
    input_path:
        Path to the .jsonl file.
    reward:
        0 or 1 — the benchmark reward for this trace.
    output_path:
        If given, write the markdown to this file as well.

    Returns
    -------
    str
        The rendered markdown.
    """
    events = []
    with open(input_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))

    turns: list[_Turn] = []
    current_turn: Optional[_Turn] = None
    current_msg_id: Optional[str] = None

    # Map tool_use id -> tool name, so we can label results
    tool_id_to_name: dict[str, str] = {}

    def _flush_turn():
        nonlocal current_turn, current_msg_id
        if current_turn is not None:
            turns.append(current_turn)
        current_turn = None
        current_msg_id = None

    def _ensure_turn(msg_id: str):
        """Start a new turn if msg_id is different from the current one."""
        nonlocal current_turn, current_msg_id
        if current_msg_id != msg_id or current_turn is None:
            _flush_turn()
            current_turn = _Turn(len(turns) + 1)
            current_msg_id = msg_id

    for event in events:
        ev_type = event.get("type", "")

        if ev_type in _SKIP_TYPES:
            continue

        if ev_type == "assistant":
            # Each assistant event that has actual content starts or continues a turn.
            message = event.get("message", {})
            msg_id = message.get("id", "")
            content = message.get("content", [])
            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")

                if btype == "thinking":
                    thinking_text = block.get("thinking", "").strip()
                    if thinking_text:
                        _ensure_turn(msg_id)
                        current_turn.add("Thinking", _sanitize(thinking_text))

                elif btype == "tool_use":
                    tool_name = block.get("name", "UnknownTool")
                    tool_id = block.get("id", "")
                    tool_input = block.get("input", {})

                    if tool_id:
                        tool_id_to_name[tool_id] = tool_name

                    _ensure_turn(msg_id)
                    rendered_input = _render_tool_input(tool_input)
                    current_turn.add(
                        f"Tool Call: {tool_name}",
                        _sanitize(rendered_input),
                    )

                elif btype == "text":
                    text = block.get("text", "").strip()
                    if text:
                        _ensure_turn(msg_id)
                        current_turn.add("Response", _sanitize(text))

        elif ev_type == "user":
            message = event.get("message", {})
            content = message.get("content", [])
            tool_use_result = event.get("toolUseResult")

            # String content (initial prompt or continuation summary)
            if isinstance(content, str):
                # This is either the initial task prompt or a context summary.
                # We include it in a special "Prompt" section, not a tool result.
                if content.strip():
                    _flush_turn()
                    current_turn = _Turn(0)  # Turn 0 = task prompt
                    current_turn.add("Task Prompt", _sanitize(content.strip()))
                    _flush_turn()
                continue

            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")

                if btype == "tool_result":
                    # Associate result with the current (most recent) turn
                    tool_use_id = block.get("tool_use_id", "")
                    tool_name = tool_id_to_name.get(tool_use_id, "Tool")
                    is_error = block.get("is_error", False)

                    # Prefer toolUseResult (richer) when available
                    if tool_use_result is not None:
                        result_text = _render_tooluse_result(tool_use_result)
                    else:
                        result_text = _render_tool_result(block.get("content", ""))

                    if current_turn is None:
                        # Result without a preceding turn — attach to previous
                        if turns:
                            target = turns[-1]
                        else:
                            current_turn = _Turn(len(turns) + 1)
                            target = current_turn
                    else:
                        target = current_turn

                    heading = "Tool Result (error)" if is_error else "Tool Result"
                    target.add(heading, result_text)

                elif btype == "document":
                    # Binary document (e.g. PDF) — note its presence
                    source = block.get("source", {})
                    media_type = source.get("media_type", "unknown")
                    # Don't dump base64 — just note it
                    note = f"[document: {media_type}]"
                    if current_turn is not None:
                        current_turn.add("Tool Result", note)
                    elif turns:
                        turns[-1].add("Tool Result", note)

    # Flush any remaining turn
    _flush_turn()

    # Render markdown — renumber assistant turns sequentially from 1
    md_parts = [f"# Agent Trace (reward: {reward})", ""]

    assistant_turn_num = 0
    for turn in turns:
        if turn.index == 0:
            # Task prompt — render with a special heading (not a numbered Turn)
            rendered = turn.render()
        else:
            assistant_turn_num += 1
            turn.index = assistant_turn_num
            rendered = turn.render()
        if rendered:
            md_parts.append(rendered)
            md_parts.append("")

    markdown = "\n".join(md_parts).rstrip() + "\n"

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(markdown, encoding="utf-8")

    return markdown


# Canonical location is agent.results — re-export for backward compatibility
from agent.results import extract_metrics_from_jsonl  # noqa: F401


def _main():
    parser = argparse.ArgumentParser(
        description="Convert a Harbor .jsonl session log to clean markdown."
    )
    parser.add_argument("--input", required=True, help="Path to input .jsonl file")
    parser.add_argument("--output", default=None, help="Path to write output .md file")
    parser.add_argument(
        "--reward",
        type=int,
        choices=[0, 1],
        required=True,
        help="Benchmark reward (0 or 1)",
    )
    args = parser.parse_args()

    md = preprocess_trace(
        input_path=args.input,
        reward=args.reward,
        output_path=args.output,
    )

    if args.output:
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(md)


if __name__ == "__main__":
    _main()
