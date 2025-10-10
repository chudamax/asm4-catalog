#!/usr/bin/env python3
"""Utility for running tool adapters locally during development."""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional


RUNTIME_PATH = Path(__file__).resolve().parent / "runtime"
if RUNTIME_PATH.exists():
    sys.path.insert(0, str(RUNTIME_PATH))

from adapter_runtime import load_adapter


def _to_file_url(path: Path) -> str:
    return f"file://{path}"  # paths are absolute already


def _read_events(events_path: Path):
    if not events_path.exists():
        return []
    with gzip.open(events_path, "rt", encoding="utf-8") as fp:
        return [json.loads(line) for line in fp if line.strip()]


def run_adapter(adapter_spec: str, inputs: Path, manifest: Optional[Path], keep: bool) -> int:
    adapter = load_adapter(adapter_spec)

    env_updates: Dict[str, str] = {
        "INPUTS_URL": _to_file_url(inputs.resolve()),
        "RUN_ID": os.getenv("RUN_ID", "local-run"),
        "BATCH_ID": os.getenv("BATCH_ID", "local-batch"),
        "TENANT_ID": os.getenv("TENANT_ID", "local"),
        "TOOL": adapter.TOOL or "",
        "TOOL_VERSION": adapter.TOOL_VERSION or "",
        "SIGNAL_URL": "",
        "OCS_PREFIX": "",
    }

    tmp_dir = Path(tempfile.mkdtemp(prefix="adapter-test-"))
    output_path = tmp_dir / "events.jsonl.gz"
    env_updates["OUTPUT_URL"] = _to_file_url(output_path.resolve())

    if manifest:
        env_updates["RESOURCES_MANIFEST_URL"] = _to_file_url(manifest.resolve())

    if keep:
        env_updates["ADAPTER_PRESERVE_WORKDIR"] = "1"

    old_env = {key: os.environ.get(key) for key in env_updates}
    try:
        os.environ.update(env_updates)
        exit_code = adapter.run()
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    events = _read_events(output_path)
    if events:
        print(json.dumps({"event_count": len(events)}, indent=2))
        for event in events:
            print(json.dumps(event, separators=(",", ":")))
    else:
        print("No events emitted.")

    if keep:
        print(f"Workdir preserved at {tmp_dir}")
    else:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an adapter locally and inspect its output")
    parser.add_argument("--adapter", required=True, help="Adapter spec in module:Class form")
    parser.add_argument("--inputs", required=True, type=Path, help="Path to newline-delimited inputs file")
    parser.add_argument("--manifest", type=Path, help="Optional manifest file for configuration")
    parser.add_argument("--keep-workdir", action="store_true", help="Preserve temporary files for debugging")
    args = parser.parse_args()

    return run_adapter(args.adapter, args.inputs.resolve(), args.manifest, args.keep_workdir)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
