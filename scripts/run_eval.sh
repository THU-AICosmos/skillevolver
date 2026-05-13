#!/bin/bash
# scripts/run_eval.sh — sweep launcher for the SkillEvolver pipeline.
#
# Runs `python -m agent.run --train-split` over a list of SkillsBench tasks.
# By default it auto-discovers every task directory in bench-assets/tasks-train/;
# you can also pass an explicit task list via TASKS=task1,task2,...
#
# Usage:
#   bash scripts/run_eval.sh <harbor_tmux_window> [start_idx] [end_idx]
#   TASKS=offer-letter-generator,court-form-filling bash scripts/run_eval.sh skillsbench:0
#   bash scripts/run_eval.sh --iterations 1 skillsbench:0     # N=1 ablation (no refinement)
#
# Launch convention: open two tmux windows. Run THIS script from the *agent*
# window. The first positional arg names the *Harbor* window — run_and_wait.py
# uses `tmux send-keys` to inject `harbor run` commands there, so the two
# windows must be different or shells will collide.
#
# Per-run budget / max-turns are set in the case statement below — edit there
# so every call in a sweep is reproducible.

set -euo pipefail
cd "$(dirname "$0")/.."

if [ -n "${TASKS:-}" ]; then
  IFS=',' read -r -a ALL_TASKS <<< "$TASKS"
else
  mapfile -t ALL_TASKS < <(find bench-assets/tasks-train -maxdepth 1 -mindepth 1 -type d -printf '%f\n' | sort)
fi

VERSION="evolver"
ITERATIONS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --iterations) ITERATIONS="--iterations $2"; shift 2 ;;
    *) break ;;
  esac
done

TMUX_WINDOW="${1:?usage: run_eval.sh [--version <name>] [--iterations N] <harbor_tmux_window> [start_idx] [end_idx]}"
START_FROM="${2:-1}"
END_AT="${3:-${#ALL_TASKS[@]}}"

MODEL="claude-opus-4-6"

case "$VERSION" in
  evolver)
    MAX_BUDGET=15
    MAX_TURNS=200
    ;;
  *)
    echo "Unknown --version: $VERSION. Only 'evolver' is supported." >&2
    exit 1
    ;;
esac

LOG_TAG="${TMUX_WINDOW//:/_}"
BATCH_LOG="scripts/run_eval_${LOG_TAG}.log"

echo "========================================" | tee -a "$BATCH_LOG"
echo "run_eval batch started: $(date)"           | tee -a "$BATCH_LOG"
echo "Window: $TMUX_WINDOW   Tasks: #$START_FROM-#$END_AT of ${#ALL_TASKS[@]}" | tee -a "$BATCH_LOG"
echo "Model: $MODEL  Budget: \$$MAX_BUDGET  Max turns: $MAX_TURNS  Version: $VERSION" | tee -a "$BATCH_LOG"
echo "========================================" | tee -a "$BATCH_LOG"

PASSED=0
FAILED=0

for i in "${!ALL_TASKS[@]}"; do
  idx=$((i + 1))
  task="${ALL_TASKS[$i]}"

  if [ "$idx" -lt "$START_FROM" ] || [ "$idx" -gt "$END_AT" ]; then
    continue
  fi

  echo "" | tee -a "$BATCH_LOG"
  echo "[$idx/${#ALL_TASKS[@]}] START $task at $(date)" | tee -a "$BATCH_LOG"

  if PYTHONUNBUFFERED=1 python -m agent.run \
       --task "$task" \
       --version "$VERSION" \
       --train-split \
       --model "$MODEL" \
       --max-budget "$MAX_BUDGET" \
       --max-turns "$MAX_TURNS" \
       --tmux-window "$TMUX_WINDOW" $ITERATIONS 2>&1 | tee -a "$BATCH_LOG"; then
    echo "[$idx/${#ALL_TASKS[@]}] DONE $task at $(date)" | tee -a "$BATCH_LOG"
    ((PASSED++)) || true
  else
    echo "[$idx/${#ALL_TASKS[@]}] FAILED $task at $(date) (exit $?)" | tee -a "$BATCH_LOG"
    ((FAILED++)) || true
  fi
done

echo "" | tee -a "$BATCH_LOG"
echo "========================================" | tee -a "$BATCH_LOG"
echo "run_eval batch complete on $TMUX_WINDOW: $(date)" | tee -a "$BATCH_LOG"
echo "Passed: $PASSED  Failed: $FAILED" | tee -a "$BATCH_LOG"
echo "========================================" | tee -a "$BATCH_LOG"
