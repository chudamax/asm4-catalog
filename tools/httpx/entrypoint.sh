#!/usr/bin/env bash
set -euo pipefail
echo "[httpx adapter] starting..."
# Simulate reading targets and producing JSONL output
echo '{"type":"http.title@v1","url":"http://example.com","title":"Example Domain"}' > /tmp/results.jsonl
echo "[httpx adapter] done."
