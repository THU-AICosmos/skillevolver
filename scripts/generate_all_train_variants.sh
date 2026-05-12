#!/bin/bash
# scripts/generate_all_train_variants.sh
# Generate training variants for ALL 56 remaining tasks in 2 parallel batches.
#
# Usage:
#   bash scripts/generate_all_train_variants.sh 1    # batch 1 (28 tasks)
#   bash scripts/generate_all_train_variants.sh 2    # batch 2 (28 tasks)
#
# Run both in parallel across tmux windows:
#   tmux new-window -t skillsbench "bash scripts/generate_all_train_variants.sh 1 2>&1 | tee scripts/gen_batch1.log"
#   tmux new-window -t skillsbench "bash scripts/generate_all_train_variants.sh 2 2>&1 | tee scripts/gen_batch2.log"

set -e
cd "$(dirname "$0")/.."
conda activate skillsbench 2>/dev/null || true

BATCH=${1:?Usage: $0 <batch 1|2>}

# 5 tasks that need --force (existing but low-quality variants)
FORCE_REGEN=(
  court-form-filling
  crystallographic-wyckoff-position-analysis
  earthquake-plate-calculation
  find-topk-similiar-chemicals
  travel-planning
)

BATCH1=(
  3d-scan-calc
  azure-bgp-oscillation-route-leak
  citation-check
  civ6-adjacency-optimizer
  court-form-filling
  crystallographic-wyckoff-position-analysis
  dialogue-parser
  dynamic-object-aware-egomotion
  earthquake-plate-calculation
  econ-detrending-correlation
  energy-market-pricing
  enterprise-information-search
  financial-modeling-qa
  find-topk-similiar-chemicals
  fix-build-agentops
  fix-build-google-auto
  fix-erlang-ssh-cve
  fix-visual-stability
  gh-repo-analytics
  glm-lake-mendota
  gravitational-wave-detection
  hvac-control
  lab-unit-harmonization
  lake-warming-attribution
  latex-formula-extraction
  lean4-proof
  mars-clouds-clustering
  mhc-layer-impl
)

BATCH2=(
  parallel-tfidf-search
  pddl-tpp-planning
  pdf-excel-diff
  pedestrian-traffic-counting
  pg-essay-to-audiobook
  powerlifting-coef-calc
  python-scala-translation
  quantum-numerical-simulation
  r2r-mpc-control
  react-performance-debugging
  reserves-at-risk-calc
  scheduling-email-assistant
  seismic-phase-picking
  shock-analysis-demand
  shock-analysis-supply
  simpo-code-reproduction
  speaker-diarization-subtitles
  spring-boot-jakarta-migration
  suricata-custom-exfil
  syzkaller-ppdev-syzlang
  threejs-to-obj
  travel-planning
  trend-anomaly-causal-inference
  video-filler-word-remover
  video-silence-remover
  video-tutorial-indexer
  virtualhome-agent-planning
  xlsx-recover-data
)

case $BATCH in
  1) TASKS=("${BATCH1[@]}") ;;
  2) TASKS=("${BATCH2[@]}") ;;
  *) echo "Invalid batch: $BATCH (use 1 or 2)"; exit 1 ;;
esac

TOTAL=${#TASKS[@]}
echo "=== Batch $BATCH: $TOTAL tasks ==="
echo "Start: $(date)"

PASS=0
FAIL=0

for i in "${!TASKS[@]}"; do
  task="${TASKS[$i]}"
  echo ""
  echo "--- [$((i+1))/$TOTAL] $task ---"

  FORCE_FLAG=""
  for ft in "${FORCE_REGEN[@]}"; do
    if [ "$task" = "$ft" ]; then
      FORCE_FLAG="--force"
      echo "  (force-regenerating: existing variant has quality issues)"
      break
    fi
  done

  if python scripts/generate_train_variant.py --task "$task" --model claude-opus-4-6 --max-budget 5.0 $FORCE_FLAG; then
    PASS=$((PASS+1))
  else
    echo "FAILED: $task"
    FAIL=$((FAIL+1))
  fi
done

echo ""
echo "=== Batch $BATCH complete ==="
echo "Pass: $PASS, Fail: $FAIL"
echo "End: $(date)"
