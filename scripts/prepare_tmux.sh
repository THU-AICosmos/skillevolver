#!/usr/bin/env bash
# Create a tmux session+window where the agent can dispatch Harbor commands
# via `tmux send-keys`. Propagates the auth env vars from the calling shell
# into the tmux environment so `harbor run` works inside that window.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="${SESSION:-skillsbench}"
WINDOW="${WINDOW:-1}"

if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
  echo "ERROR: set ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN in the current shell" >&2
  exit 1
fi

tmux has-session -t "$SESSION" 2>/dev/null || tmux new-session -d -s "$SESSION" -n shell
if ! tmux list-windows -t "$SESSION" -F '#I' | grep -qx "$WINDOW"; then
  tmux new-window -d -t "$SESSION:$WINDOW" -n harbor
fi

EXPORT_CMD=""
for var in ANTHROPIC_API_KEY CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN; do
  val="${!var:-}"
  [ -z "$val" ] && continue
  tmux set-environment -t "$SESSION" "$var" "$val"
  [ -n "$EXPORT_CMD" ] && EXPORT_CMD="$EXPORT_CMD && "
  EXPORT_CMD="${EXPORT_CMD}export $var='$val'"
done

tmux send-keys -t "$SESSION:$WINDOW" "$EXPORT_CMD && cd $ROOT/Benchmarks/skillsbench" C-m
echo "tmux ready at $SESSION:$WINDOW"
