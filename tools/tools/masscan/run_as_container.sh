#!/usr/bin/env bash
set -euo pipefail

trap 'echo ""; echo "ERROR at line $LINENO: $BASH_COMMAND"; exit 1' ERR

ADAPTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$ADAPTER_DIR/../../.." && pwd)"
IMAGE="${IMAGE:-asm/masscan}"
WORK="${WORK:-/tmp/asm-masscan-local}"

echo "[run] ADAPTER_DIR=$ADAPTER_DIR"
echo "[run] ROOT=$ROOT"
echo "[run] IMAGE=$IMAGE"
echo "[run] WORK=$WORK"

mkdir -p "$WORK"

cp "$ADAPTER_DIR/fixtures/inputs.txt" "$WORK/inputs.txt"
cp "$ADAPTER_DIR/fixtures/inputs.manifest.json" "$WORK/inputs.manifest.json"

rm -f "$WORK/events.jsonl.gz" "$WORK/container.log"

echo "[run] Launching container..."
set -x
docker run --rm \
  --cap-add NET_RAW --cap-add NET_ADMIN \
  --network host \
  -v "$WORK:/work" \
  -e TENANT_ID=local \
  -e RUN_ID=local-run \
  -e BATCH_ID=local-batch \
  -e INPUTS_URL=file:///work/inputs.txt \
  -e RESOURCES_MANIFEST_URL=file:///work/inputs.manifest.json \
  -e OUTPUT_URL=file:///work/events.jsonl.gz \
  "$IMAGE" 2>&1 | tee "$WORK/container.log"
set +x

echo "[run] Container finished. Checking output..."
ls -la "$WORK" || true

if [[ ! -s "$WORK/events.jsonl.gz" ]]; then
  echo "[run] ERROR: events.jsonl.gz was not created or is empty."
  echo "[run] Last 200 lines of container log:"
  tail -n 200 "$WORK/container.log" || true
  exit 2
fi

echo "[run] Output OK. First lines:"
gzip -dc "$WORK/events.jsonl.gz" | head -n 20
