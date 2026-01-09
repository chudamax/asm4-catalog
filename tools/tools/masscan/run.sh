#!/usr/bin/env bash
set -euo pipefail

trap 'echo ""; echo "ERROR at line $LINENO: $BASH_COMMAND"; exit 1' ERR

ADAPTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="${WORK:-/tmp/asm-masscan-local}"

echo "[run] ADAPTER_DIR=$ADAPTER_DIR"
echo "[run] WORK=$WORK"

mkdir -p "$WORK"

cp "$ADAPTER_DIR/fixtures/inputs.txt" "$WORK/inputs.txt"
cp "$ADAPTER_DIR/fixtures/inputs.manifest.json" "$WORK/inputs.manifest.json"

rm -f "$WORK/events.jsonl.gz" "$WORK/adapter.log"

export INPUTS_URL="file://$WORK/inputs.txt"
export RESOURCES_MANIFEST_URL="file://$WORK/inputs.manifest.json"
export OUTPUT_URL="file://$WORK/events.jsonl.gz"

set -x
python3 -m asm_adapter_runtime.cli --adapter masscan_adapter:MasscanAdapter 2>&1 | tee "$WORK/adapter.log"
set +x

echo "[run] Adapter finished. Checking output..."
ls -la "$WORK" || true

if [[ ! -s "$WORK/events.jsonl.gz" ]]; then
  echo "[run] ERROR: events.jsonl.gz was not created or is empty."
  echo "[run] Last 200 lines of adapter log:"
  tail -n 200 "$WORK/adapter.log" || true
  exit 2
fi

echo "[run] Output OK. First lines:"
gzip -dc "$WORK/events.jsonl.gz" | head -n 20
