#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="${SESSION:-skillsbench}"
WINDOW="${WINDOW:-1}"

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ERROR: ANTHROPIC_API_KEY is not set in the current shell" >&2
  exit 1
fi

tmux has-session -t "$SESSION" 2>/dev/null || tmux new-session -d -s "$SESSION" -n shell
if ! tmux list-windows -t "$SESSION" -F '#I' | grep -qx "$WINDOW"; then
  tmux new-window -d -t "$SESSION:$WINDOW" -n harbor
fi
tmux set-environment -t "$SESSION" ANTHROPIC_API_KEY "$ANTHROPIC_API_KEY"
if [ -n "${ANTHROPIC_BASE_URL:-}" ]; then
  tmux set-environment -t "$SESSION" ANTHROPIC_BASE_URL "$ANTHROPIC_BASE_URL"
fi
if [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
  tmux set-environment -t "$SESSION" ANTHROPIC_AUTH_TOKEN "$ANTHROPIC_AUTH_TOKEN"
fi

EXPORT_CMD="export ANTHROPIC_API_KEY='$ANTHROPIC_API_KEY'"
if [ -n "${ANTHROPIC_BASE_URL:-}" ]; then
  EXPORT_CMD="$EXPORT_CMD && export ANTHROPIC_BASE_URL='$ANTHROPIC_BASE_URL'"
fi
if [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
  EXPORT_CMD="$EXPORT_CMD && export ANTHROPIC_AUTH_TOKEN='$ANTHROPIC_AUTH_TOKEN'"
fi
tmux send-keys -t "$SESSION:$WINDOW" "$EXPORT_CMD && cd $ROOT/Benchmarks/skillsbench" C-m
echo "tmux ready at $SESSION:$WINDOW"
echo "verify with: tmux show-environment -t $SESSION ANTHROPIC_API_KEY"
