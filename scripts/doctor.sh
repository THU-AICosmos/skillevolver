#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAILURES=0

pass() { printf '[PASS] %s\n' "$1"; }
fail() { printf '[FAIL] %s\n' "$1"; FAILURES=$((FAILURES + 1)); }

for cmd in claude uv tmux docker git rsync; do
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "found command: $cmd"
  else
    fail "missing command: $cmd"
  fi
done

if command -v conda >/dev/null 2>&1; then
  pass "found command: conda"
elif [ -x "$ROOT/.venv/bin/python" ]; then
  pass "project .venv present"
else
  fail "missing conda and project .venv"
fi

[ -d "$ROOT/bench-assets/tasks-train" ] && pass "overlay source present" || fail "missing bench-assets/tasks-train"
[ -f "$ROOT/Benchmarks/skillsbench/pyproject.toml" ] && pass "skillsbench repo present" || fail "skillsbench not cloned — run scripts/setup.sh"
[ -f "$ROOT/Benchmarks/skillsbench/.venv/bin/harbor" ] && pass "skillsbench uv env present" || fail "skillsbench .venv missing"
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  pass "ANTHROPIC_API_KEY exported"
elif [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
  pass "CLAUDE_CODE_OAUTH_TOKEN exported (Claude Max subscription auth)"
else
  fail "neither ANTHROPIC_API_KEY nor CLAUDE_CODE_OAUTH_TOKEN is set (need one)"
fi

if [ -f "$ROOT/Benchmarks/skillsbench/.venv/lib/python3.12/site-packages/harbor/models/trial/config.py" ]; then
  if command -v rg >/dev/null 2>&1; then
    MATCH_CMD=(rg -q 'trial_index: int = 0')
  else
    MATCH_CMD=(grep -q 'trial_index: int = 0')
  fi
  if "${MATCH_CMD[@]}" "$ROOT/Benchmarks/skillsbench/.venv/lib/python3.12/site-packages/harbor/models/trial/config.py"; then
    pass "Harbor trial_index patch present"
  else
    fail "Harbor trial_index patch missing"
  fi
fi

if [ "$FAILURES" -ne 0 ]; then
  printf '\nRun: bash scripts/setup.sh\n' >&2
  exit 1
fi
