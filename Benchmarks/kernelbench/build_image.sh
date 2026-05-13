#!/usr/bin/env bash
# Build a Docker image for a KernelBench-Harbor task.
#
# Required env: TASK_NAME (e.g. kb-l1-p1-square-matrix-multiplication)
# Optional env:
#   IMAGE_REPO  Docker repo prefix (default: kb-self-evolving)
#   IMAGE_TAG   Tag (default: $TASK_NAME)
#   BUILDER     buildx builder name (default: default)
#   PUSH        1 = push to registry, 0 = load into local docker (default: 0)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KBH_ROOT="$ROOT/Benchmarks/kernelbench/tasks-train"

TASK_NAME="${TASK_NAME:-kb-l1-p1-square-matrix-multiplication}"
IMAGE_REPO="${IMAGE_REPO:-kb-self-evolving}"
IMAGE_TAG="${IMAGE_TAG:-$TASK_NAME}"
IMAGE_URI="${IMAGE_URI:-$IMAGE_REPO:$IMAGE_TAG}"
BUILDER="${BUILDER:-default}"
PUSH="${PUSH:-0}"
TASK_DIR="$KBH_ROOT/$TASK_NAME"
ENV_DIR="$TASK_DIR/environment"

if [ ! -d "$TASK_DIR" ]; then
  echo "ERROR: task not found: $TASK_DIR" >&2
  exit 1
fi

if [ ! -f "$ENV_DIR/Dockerfile" ]; then
  echo "ERROR: Dockerfile not found: $ENV_DIR/Dockerfile" >&2
  exit 1
fi

BUILD_CMD=(
  docker buildx build
  --builder "$BUILDER"
  -t "$IMAGE_URI"
)

for var in http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY; do
  val="${!var:-}"
  [ -n "$val" ] && BUILD_CMD+=(--build-arg "$var=$val")
done

if [ "$PUSH" = "1" ]; then
  BUILD_CMD+=(--push)
else
  BUILD_CMD+=(--load)
fi

BUILD_CMD+=("$ENV_DIR")

echo "Building KernelBench Harbor image"
echo "  task:    $TASK_NAME"
echo "  builder: $BUILDER"
echo "  image:   $IMAGE_URI"
echo "  mode:    $( [ "$PUSH" = "1" ] && echo push || echo load )"

"${BUILD_CMD[@]}"
