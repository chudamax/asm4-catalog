from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from adapter_runtime import BaseAdapter, BatchConfig, Heartbeat
from adapter_runtime.models import HttpResponse


class HttpxAdapter(BaseAdapter):
    TOOL = "httpx"
    TOOL_VERSION = "1.6.1"
    PRODUCES = ("http.response",)

    def __init__(self) -> None:
        self._results_seen = 0

    @property
    def binary_path(self) -> str:
        return "/usr/local/bin/httpx"

    def build_cmd(self, targets: List[str], cfg: BatchConfig, workdir: Path) -> Optional[List[str]]:
        target_file = workdir / "targets.txt"
        target_file.write_text("\n".join(targets) + ("\n" if targets else ""), encoding="utf-8")

        base_cmd = [
            self.binary_path,
            "-json",
            "-no-color",
            "-silent",
            "-l",
            str(target_file),
        ]

        params = cfg.parameters or {}
        extra_args = params.get("args") or params.get("extra_args")
        if isinstance(extra_args, list):
            base_cmd.extend(str(a) for a in extra_args)
        elif isinstance(extra_args, str):
            base_cmd.append(extra_args)

        timeout = params.get("timeout")
        if timeout:
            base_cmd.extend(["-timeout", str(timeout)])

        rate = params.get("rate")
        if rate:
            base_cmd.extend(["-rate", str(rate)])

        return base_cmd

    def parse_tool_output(self, line: str, emit, hb: Heartbeat) -> None:
        data = line.strip()
        if not data:
            return

        try:
            doc = json.loads(data)
        except json.JSONDecodeError:
            return

        event = HttpResponse.from_httpx_json(doc)
        emit(event.event_type, event.to_payload())
        self._results_seen += 1
        hb.metrics["processed_targets"] = self._results_seen
