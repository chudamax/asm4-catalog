from __future__ import annotations

import gzip
import json
from pathlib import Path

import sys

BASE_DIR = Path(__file__).resolve().parents[4]
RUNTIME_SRC = BASE_DIR / 'tools' / 'runtime' / 'adapter_runtime' / 'src'
WRAPPERS_SRC = BASE_DIR / 'tools' / 'runtime' / 'wrappers' / 'src'
ADAPTER_SRC = Path(__file__).resolve().parents[1]
for candidate in (RUNTIME_SRC, WRAPPERS_SRC, ADAPTER_SRC):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from asm_tool_wrappers.masscan_wrapper import MasscanWrapper
from masscan_adapter import MasscanAdapter


def _file_url(path: Path) -> str:
    return f"file://{path}"


def test_masscan_adapter_produces_events_file(tmp_path, monkeypatch):
    inputs_file = tmp_path / "inputs.txt"
    inputs_file.write_text("", encoding="utf-8")

    manifest = {
        "tool": "masscan",
        "tool_version": "1.3.2",
        "parameters": {},
        "resources": [],
    }
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")

    output_file = tmp_path / "events.jsonl.gz"

    monkeypatch.setenv("INPUTS_URL", _file_url(inputs_file))
    monkeypatch.setenv("RESOURCES_MANIFEST_URL", _file_url(manifest_file))
    monkeypatch.setenv("OUTPUT_URL", _file_url(output_file))
    monkeypatch.delenv("SIGNAL_URL", raising=False)

    adapter = MasscanAdapter()
    rc = adapter.run()
    assert rc == 0
    assert output_file.exists()

    with gzip.open(output_file, "rt", encoding="utf-8") as handle:
        lines = [ln.strip() for ln in handle.readlines() if ln.strip()]
    assert lines == []


def test_masscan_wrapper_emits_events(tmp_path):
    jsonl = tmp_path / "masscan.jsonl"
    jsonl.write_text(
        json.dumps([
            {
                "ip": "203.0.113.10",
                "ports": [
                    {"port": 80, "proto": "tcp", "status": "open", "service": "http"},
                    {"port": 22, "proto": "tcp", "status": "closed"},
                ],
            }
        ]),
        encoding="utf-8",
    )

    wrapper = MasscanWrapper()
    wrapper._jsonl = jsonl  # simulate build_cmd side-effect
    emitted: list[tuple[str, dict]] = []

    def capture(event):
        emitted.append((event.event_type, event.to_payload()))

    wrapper.postprocess_files(tmp_path, capture)

    assert emitted == [("network.service", {"ip": "203.0.113.10", "port": 80, "protocol": "tcp", "banner": "http"})]
