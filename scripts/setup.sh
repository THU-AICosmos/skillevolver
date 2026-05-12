#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SKILLSBENCH_URL="https://github.com/benchflow-ai/skillsbench.git"
SKILLSBENCH_DIR="$ROOT/Benchmarks/skillsbench"

# Clone SkillsBench if not present (replaces git submodule)
if [ ! -f "$SKILLSBENCH_DIR/pyproject.toml" ]; then
  echo "Cloning SkillsBench..."
  rm -rf "$SKILLSBENCH_DIR"
  git clone "$SKILLSBENCH_URL" "$SKILLSBENCH_DIR"
fi

bash scripts/sync_tasks_train.sh
( cd "$SKILLSBENCH_DIR" && uv sync )
python scripts/apply_harbor_patches.py
bash scripts/doctor.sh
