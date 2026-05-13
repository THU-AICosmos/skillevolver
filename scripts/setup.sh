#!/usr/bin/env bash
# One-shot setup: clone SkillsBench, mirror bench-assets/tasks-train/ into it,
# install the Harbor runtime, apply our Harbor patches, run the doctor check.
# Re-running this is safe — every step is idempotent.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SKILLSBENCH_URL="https://github.com/benchflow-ai/skillsbench.git"
SKILLSBENCH_DIR="$ROOT/Benchmarks/skillsbench"

if [ ! -f "$SKILLSBENCH_DIR/pyproject.toml" ]; then
  echo "Cloning SkillsBench..."
  rm -rf "$SKILLSBENCH_DIR"
  git clone "$SKILLSBENCH_URL" "$SKILLSBENCH_DIR"
fi

# Mirror bench-assets/tasks-train/ → Benchmarks/skillsbench/tasks-train/.
# Override SOURCE_DIR / TARGET_DIR to sync from a custom overlay.
SOURCE_DIR="${SOURCE_DIR:-$ROOT/bench-assets/tasks-train}"
TARGET_DIR="${TARGET_DIR:-$SKILLSBENCH_DIR/tasks-train}"
mkdir -p "$TARGET_DIR" "$SKILLSBENCH_DIR/tasks-evolved-skills"
rsync -a --delete "$SOURCE_DIR"/ "$TARGET_DIR"/
echo "Synced tasks-train: $SOURCE_DIR -> $TARGET_DIR"

( cd "$SKILLSBENCH_DIR" && uv sync )
python scripts/apply_harbor_patches.py
bash scripts/doctor.sh
