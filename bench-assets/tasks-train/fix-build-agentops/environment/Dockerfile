# Synthetic broken Python project: StatCalc-AI/statcalc
FROM python:3.10-slim

USER root

RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

# install uv
ENV PATH="/root/.local/bin:$PATH"
RUN curl -LsSf https://astral.sh/uv/0.9.22/install.sh | sh

# Create the BugSwarm-like directory structure
RUN mkdir -p /home/github/build/failed/StatCalc-AI/statcalc
RUN mkdir -p /home/github/build/passed
RUN mkdir -p /tests

# --- Create the broken Python project ---
WORKDIR /home/github/build/failed/StatCalc-AI/statcalc

# Initialize git repo
RUN git init && git config user.email "ci@statcalc.ai" && git config user.name "CI Bot"

# pyproject.toml
RUN cat > pyproject.toml <<'PYEOF'
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "statcalc"
version = "0.4.0"
description = "Statistical calculations toolkit"
requires-python = ">=3.9"

[tool.pytest.ini_options]
testpaths = ["tests"]
PYEOF

# statcalc package
RUN mkdir -p statcalc

RUN cat > statcalc/__init__.py <<'PYEOF'
from .compute import mean, median, variance, std_dev
from .render import format_table, format_summary
PYEOF

# compute.py - has TWO bugs:
# 1. NameError: 'value' instead of 'values' in mean()
# 2. median() has off-by-one: uses len(sorted_vals) instead of len(sorted_vals) - 1 for indexing,
#    but actually the bug is dividing by len-1 instead of len in variance
RUN cat > statcalc/compute.py <<'PYEOF'
"""Core statistical computation functions."""
import math
from typing import List


def mean(values: List[float]) -> float:
    """Compute the arithmetic mean of a list of numbers."""
    if not values:
        raise ValueError("Cannot compute mean of empty list")
    return sum(values) / len(value)


def median(values: List[float]) -> float:
    """Compute the median of a list of numbers."""
    if not values:
        raise ValueError("Cannot compute median of empty list")
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
    return sorted_vals[mid]


def variance(values: List[float]) -> float:
    """Compute the population variance."""
    if len(values) < 2:
        raise ValueError("Need at least 2 values for variance")
    avg = mean(values)
    return sum((x - avg) ** 2 for x in values) / len(values)


def std_dev(values: List[float]) -> float:
    """Compute the population standard deviation."""
    return math.sqrt(variance(values))
PYEOF

# render.py - has TWO bugs:
# 1. Missing 'import json' but uses json.dumps
# 2. Uses undefined variable 'header' instead of 'headers' in format_table
RUN cat > statcalc/render.py <<'PYEOF'
"""Output formatting and rendering functions."""
from typing import Any, Dict, List


def format_table(headers: List[str], rows: List[List[Any]]) -> str:
    """Format data as a simple text table."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    line = "+".join("-" * (w + 2) for w in col_widths)
    # BUG: 'header' should be 'headers'
    header_row = "|".join(f" {h:<{col_widths[i]}} " for i, h in enumerate(header))
    result = [line, header_row, line]
    for row in rows:
        row_str = "|".join(f" {str(c):<{col_widths[i]}} " for i, c in enumerate(row))
        result.append(row_str)
    result.append(line)
    return "\n".join(result)


def format_summary(stats: Dict[str, float]) -> str:
    """Format statistics summary as JSON string."""
    # BUG: json is not imported
    return json.dumps(stats, indent=2)
PYEOF

# Tests
RUN mkdir -p tests

RUN cat > tests/__init__.py <<'PYEOF'
PYEOF

RUN cat > tests/test_compute.py <<'PYEOF'
"""Tests for statistical computation functions."""
import math
import pytest
from statcalc.compute import mean, median, variance, std_dev


class TestMean:
    def test_simple(self):
        assert mean([1, 2, 3, 4, 5]) == 3.0

    def test_single(self):
        assert mean([42]) == 42.0

    def test_negative(self):
        assert mean([-1, 0, 1]) == 0.0

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            mean([])


class TestMedian:
    def test_odd_count(self):
        assert median([3, 1, 2]) == 2.0

    def test_even_count(self):
        assert median([1, 2, 3, 4]) == 2.5

    def test_single(self):
        assert median([7]) == 7.0


class TestVariance:
    def test_simple(self):
        result = variance([2, 4, 4, 4, 5, 5, 7, 9])
        assert abs(result - 4.0) < 0.01

    def test_identical(self):
        assert variance([5, 5, 5, 5]) == 0.0


class TestStdDev:
    def test_simple(self):
        result = std_dev([2, 4, 4, 4, 5, 5, 7, 9])
        assert abs(result - 2.0) < 0.01
PYEOF

RUN cat > tests/test_render.py <<'PYEOF'
"""Tests for output formatting functions."""
from statcalc.render import format_table, format_summary


class TestFormatTable:
    def test_basic(self):
        headers = ["Name", "Score"]
        rows = [["Alice", 95], ["Bob", 87]]
        result = format_table(headers, rows)
        assert "Alice" in result
        assert "Bob" in result
        assert "Score" in result

    def test_empty_rows(self):
        headers = ["Col1", "Col2"]
        result = format_table(headers, [])
        assert "Col1" in result


class TestFormatSummary:
    def test_basic(self):
        stats = {"mean": 3.0, "median": 2.5}
        result = format_summary(stats)
        assert "mean" in result
        assert "3.0" in result
PYEOF

# Commit everything so git apply works
RUN git add -A && git commit -m "Initial commit with build errors"

# --- Create the run_passed.sh test runner ---
RUN cat > /tests/run_passed.sh <<'RUNEOF'
#!/bin/bash
set -e
cd /home/github/build/passed/StatCalc-AI/statcalc
pip install -e . 2>/dev/null || true
python -m pytest tests/ -v --tb=short
RUNEOF
RUN chmod +x /tests/run_passed.sh

# Copy skills to agent-specific locations
COPY skills /root/.claude/skills
COPY skills /root/.codex/skills
COPY skills /root/.opencode/skill
COPY skills /root/.goose/skills
COPY skills /root/.factory/skills
COPY skills /root/.agents/skills
COPY skills /root/.gemini/skills

WORKDIR /home/github/build
