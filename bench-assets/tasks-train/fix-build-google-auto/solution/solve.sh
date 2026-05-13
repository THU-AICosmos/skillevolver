#!/bin/bash

set -euo pipefail

BUILD_DIR=/home/travis/build
REPO_ID="${REPO_ID:-google/auto}"
IMAGE_TAG="${bugswarm_image_tag:-google-auto-101506036}"
REPO_DIR="$BUILD_DIR/failed/$REPO_ID"
NOTE_PATH="$BUILD_DIR/failed/diagnosis_report.txt"
WORK_DIR="$BUILD_DIR/fixes"

mkdir -p "$WORK_DIR"

echo "Fetched BugSwarm patch set for $REPO_ID and applied it with git apply." > "$NOTE_PATH"

if [ ! -d "$REPO_DIR" ]; then
    echo "Repository directory does not exist: $REPO_DIR" >&2
    exit 1
fi

cd "$WORK_DIR"
echo "Oracle agent working in $(pwd)"
uv init --python 3.10
uv add bugswarm-common==2024.8.26

cat <<'PYEOF' > fetch_diffs.py
import os
from bugswarm.common.rest_api.database_api import DatabaseAPI

image_tag = os.environ["bugswarm_image_tag"]
repo_dir = os.environ["REPO_DIR"]

bugswarm_client = DatabaseAPI()
diff = bugswarm_client.get_diff(image_tag)

for i, patch in enumerate(diff["patches"]):
    path = os.path.join(repo_dir, f"fix_{i}.diff")
    with open(path, "w") as f:
        f.write(patch["content"])
PYEOF

REPO_DIR="$REPO_DIR" bugswarm_image_tag="$IMAGE_TAG" uv run fetch_diffs.py

cd "$REPO_DIR"
echo "Oracle agent working in $(pwd)"

for patch in fix_*.diff; do
    if [ ! -f "$patch" ]; then
        echo "No fix_*.diff files found in $REPO_DIR" >&2
        exit 1
    fi
    echo "Applying patch: $patch"
    git apply "$patch"
    echo "--------------------------------"
done
