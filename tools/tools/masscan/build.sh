#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TOOL="masscan"
DOCKERFILE="$ROOT/tools/tools/$TOOL/Dockerfile"
IMAGE_DEV="asm/$TOOL"

docker build -f "$DOCKERFILE" -t "$IMAGE_DEV" "$ROOT"

echo "Built $IMAGE_DEV"
