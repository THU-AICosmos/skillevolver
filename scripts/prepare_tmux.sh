#!/usr/bin/env bash
# Create a tmux session+window where Harbor can run trial commands. The
# agent dispatches `harbor run` into this window via `tmux send-keys`, so
# this script only sets up the session — it does NOT export your API key.
# After this runs, attach with `tmux attach -t harbor` (or the SESSION you
# overrode), export ANTHROPIC_API_KEY in that window, and detach.
#
# Override SESSION / WINDOW env vars to use different names.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="${SESSION:-harbor}"
WINDOW="${WINDOW:-0}"

tmux has-session -t "$SESSION" 2>/dev/null || tmux new-session -d -s "$SESSION" -n shell
if ! tmux list-windows -t "$SESSION" -F '#I' | grep -qx "$WINDOW"; then
  tmux new-window -d -t "$SESSION:$WINDOW" -n harbor
fi

tmux send-keys -t "$SESSION:$WINDOW" "cd $ROOT/Benchmarks/skillsbench" C-m

cat <<EOF
tmux ready at $SESSION:$WINDOW

Next: attach to this window and export your API key inside it.
  tmux attach -t $SESSION
  # (switch to window $WINDOW with Ctrl-b $WINDOW)
  export ANTHROPIC_API_KEY="sk-..."
  # then detach with Ctrl-b d
EOF
