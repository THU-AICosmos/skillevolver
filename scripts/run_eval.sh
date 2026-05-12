#!/bin/bash
# scripts/run_eval.sh — canonical SkillsBench evaluation sweep launcher.
#
# Runs the SkillEvolver pipeline with --train-split over the 81 Harbor-runnable
# SkillsBench tasks. Tasks are **ordered by category** (A → B1 → B2 → B3 → C1
# → C2 → D → uncat), so you can run a single category by passing explicit
# index ranges.
#
# Excluded from this array (and never counted in 81): 6 tasks that need paid
# third-party APIs the agent can't access —
#   - video-tutorial-indexer, video-filler-word-remover, gh-repo-analytics,
#     scheduling-email-assistant, pg-essay-to-audiobook, mhc-layer-impl.
#
# Usage:
#   bash scripts/run_eval.sh [--iterations N] <tmux_window> [start_idx] [end_idx]
#   bash scripts/run_eval.sh skillsbench:0 1 10              # first 10 tasks
#   bash scripts/run_eval.sh --iterations 1 skillsbench:0    # no-refinement ablation (N=1)
#
# Per-run budget/turns are set by the CASE below — DO NOT override with
# --max-budget flags from the shell, edit HERE so every call is reproducible.
#
# Launch convention: open two tmux windows (e.g. `agent:0` and `harbor:0`).
# Run THIS script from the agent window. The --tmux-window arg below tells
# run_and_wait.py which window to send `harbor run` commands into. The
# Harbor window must be DIFFERENT from the agent window — run_and_wait.py
# uses `tmux send-keys` to inject harbor commands and would collide with
# the agent's own shell otherwise. The first positional arg ($1) is the
# Harbor tmux window (e.g. `harbor:0`).
#
# Results go to evolved-skills/<task>/<timestamp>/.
# Logs append to scripts/run_eval_<window>.log (slashes replaced with underscores).

set -euo pipefail
cd "$(dirname "$0")/.."

# ---------------------------------------------------------------------------
# Task list — 81 Harbor-runnable SkillsBench tasks, ordered by category.
# Category index ranges:
#   A   (Easy — O46 ≥0.8 no-skill)           : 1-19   (19 tasks, pg-essay excluded as paid-API)
#   B1  (Struggling + Skills Help)           : 20-33  (14 tasks)
#   B2  (Struggling + Skills Neutral)        :  34-35 ( 2 tasks)
#   B3  (Struggling + Skills Hurt)           : 36-42  ( 7 tasks)
#   C1  (Skill-Unlocked Strong)              : 43-53  (11 tasks)
#   C2  (Skill-Unlocked Weak)                : 54-59  ( 6 tasks)
#   D   (Hopeless, runnable subset)          : 60-79  (20 tasks, 4 paid-API excluded)
#   ?   (Uncategorized in paper)             : 80-81  ( 2 tasks)
# ---------------------------------------------------------------------------

ALL_TASKS=(
  # ==== A — Easy, 19 tasks (indices 1-19) ====
  glm-lake-mendota                              #   1  A
  mars-clouds-clustering                        #   2  A
  threejs-to-obj                                #   3  A
  lake-warming-attribution                      #   4  A
  syzkaller-ppdev-syzlang                       #   5  A
  econ-detrending-correlation                   #   6  A
  lab-unit-harmonization                        #   7  A
  citation-check                                #   8  A
  spring-boot-jakarta-migration                 #   9  A
  powerlifting-coef-calc                        #  10  A
  3d-scan-calc                                  #  11  A
  dialogue-parser                               #  12  A
  lean4-proof                                   #  13  A
  energy-market-pricing                         #  14  A
  fix-erlang-ssh-cve                            #  15  A
  pdf-excel-diff                                #  16  A
  parallel-tfidf-search                         #  17  A
  trend-anomaly-causal-inference                #  18  A   (network: pip from GH)
  hvac-control                                  #  19  A

  # ==== B1 — Struggling + Skills Help, 14 tasks (indices 20-33) ====
  offer-letter-generator                        #  20  B1  ⚠ DSTLR get-pip.py bootstrap 404
  flood-risk-analysis                           #  21  B1  ⚠ DSTLR Harbor trial dropout (0/2 exp)
  court-form-filling                            #  22  B1
  invoice-fraud-detection                       #  23  B1
  multilingual-video-dubbing                    #  24  B1  ⚠ DSTLR get-pip.py bootstrap 404
  software-dependency-audit                     #  25  B1
  fix-druid-loophole-cve                        #  26  B1  ⚠ DSTLR get-pip.py bootstrap 404
  jax-computing-basics                          #  27  B1
  data-to-d3                                    #  28  B1  (network: npm install)
  adaptive-cruise-control                       #  29  B1
  paper-anonymizer                              #  30  B1
  grid-dispatch-operator                        #  31  B1
  exceltable-in-ppt                             #  32  B1
  organize-messy-files                          #  33  B1

  # ==== B2 — Struggling + Skills Neutral, 2 tasks (indices 34-35) ====
  crystallographic-wyckoff-position-analysis    #  34  B2
  exoplanet-detection-period                    #  35  B2

  # ==== B3 — Struggling + Skills Hurt, 7 tasks (indices 36-42) ====
  earthquake-phase-association                  #  36  B3
  travel-planning                               #  37  B3
  jpg-ocr-stat                                  #  38  B3
  find-topk-similiar-chemicals                  #  39  B3
  energy-ac-optimal-power-flow                  #  40  B3
  flink-query                                   #  41  B3
  taxonomy-tree-merge                           #  42  B3  ⚠ DSTLR Harbor 0/0 trials

  # ==== C1 — Skill-Unlocked Strong, 11 tasks (indices 43-53) ====
  protein-expression-analysis                   #  43  C1
  dapt-intrusion-detection                      #  44  C1  ⚠ DSTLR incomplete pipeline
  pptx-reference-formatting                     #  45  C1
  mario-coin-counting                           #  46  C1
  sales-pivot-analysis                          #  47  C1
  sec-financial-report                          #  48  C1
  manufacturing-fjsp-optimization               #  49  C1
  earthquake-plate-calculation                  #  50  C1  ⚠ DSTLR incomplete, pollution recovery
  weighted-gdp-calc                             #  51  C1  (was nested skills/ pollution recovery)
  manufacturing-equipment-maintenance           #  52  C1  ⚠ DSTLR handbook.pdf >1MB crashes Agent SDK reader
  fix-build-agentops                            #  53  C1  ⚠ DSTLR ~10GB BugSwarm image pull + incomplete

  # ==== C2 — Skill-Unlocked Weak, 6 tasks (indices 54-59) ====
  simpo-code-reproduction                       #  54  C2  (pollution recovery)
  setup-fuzzing-py                              #  55  C2  (large gcr.io image)
  manufacturing-codebook-normalization          #  56  C2
  threejs-structure-parser                      #  57  C2
  r2r-mpc-control                               #  58  C2
  azure-bgp-oscillation-route-leak              #  59  C2

  # ==== D — Hopeless but runnable, 20 tasks (indices 60-79) ====
  python-scala-translation                      #  60  D
  civ6-adjacency-optimizer                      #  61  D
  virtualhome-agent-planning                    #  62  D
  dynamic-object-aware-egomotion                #  63  D
  pedestrian-traffic-counting                   #  64  D   (needs ANTHROPIC_API_KEY — we have it)
  fix-build-google-auto                         #  65  D   (~10GB BugSwarm image)
  suricata-custom-exfil                         #  66  D   (non-stock base image)
  enterprise-information-search                 #  67  D
  financial-modeling-qa                         #  68  D
  speaker-diarization-subtitles                 #  69  D   ⚠ DSTLR incomplete + torch.hub Silero download + trajectory lost
  pddl-tpp-planning                             #  70  D
  gravitational-wave-detection                  #  71  D
  shock-analysis-supply                         #  72  D
  shock-analysis-demand                         #  73  D
  seismic-phase-picking                         #  74  D   (SeisBench weights download)
  latex-formula-extraction                      #  75  D   ⚠ DSTLR incomplete pipeline
  reserves-at-risk-calc                         #  76  D   (network: IMF download)
  react-performance-debugging                   #  77  D   (multi-container compose)
  quantum-numerical-simulation                  #  78  D
  xlsx-recover-data                             #  79  D

  # ==== Uncategorized in o46-s45 doc, 2 tasks (indices 80-81) ====
  fix-visual-stability                          #  80  ?   (multi-container docker-compose)
  video-silence-remover                         #  81  ?

  # NON-RUNNABLE — paid external APIs (NOT in this array, listed for docs only):
  #   video-tutorial-indexer, video-filler-word-remover, gh-repo-analytics,
  #   scheduling-email-assistant, pg-essay-to-audiobook, mhc-layer-impl
)

# ---------------------------------------------------------------------------
# Argument parsing — optional flags first, then positional args
# ---------------------------------------------------------------------------
VERSION="evolver"
ITERATIONS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --iterations) ITERATIONS="--iterations $2"; shift 2 ;;
    *) break ;;
  esac
done

TMUX_WINDOW="${1:?usage: run_eval.sh [--version <name>] <tmux_window> [start_idx] [end_idx]}"
START_FROM="${2:-1}"
END_AT="${3:-${#ALL_TASKS[@]}}"

MODEL="claude-opus-4-6"

# Per-version budget/turns. These override any hard-coded default so that
# cross-version comparisons use the same launcher. If you need to tune,
# edit HERE, not via command-line flags.
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
SKIPPED=0

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
echo "Passed: $PASSED  Failed: $FAILED  Skipped: $SKIPPED" | tee -a "$BATCH_LOG"
echo "========================================" | tee -a "$BATCH_LOG"
