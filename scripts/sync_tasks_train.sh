#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${SOURCE_DIR:-$ROOT/bench-assets/tasks-train}"
TARGET_DIR="${TARGET_DIR:-$ROOT/Benchmarks/skillsbench/tasks-train}"
EVOLVED_DIR="$ROOT/Benchmarks/skillsbench/tasks-evolved-skills"

if [ ! -d "$SOURCE_DIR" ]; then
  echo "ERROR: source overlay not found at $SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
mkdir -p "$EVOLVED_DIR"
rsync -a --delete "$SOURCE_DIR"/ "$TARGET_DIR"/

echo "Synced tasks-train overlay:"
echo "  source: $SOURCE_DIR"
echo "  target: $TARGET_DIR"
