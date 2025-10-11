import json
from typing import List, Optional
from pathlib import Path
from adapter_runtime.base import BaseAdapter, BatchConfig, Heartbeat
from models import HttpResponse, emit_event

class HttpxAdapter(BaseAdapter):
    TOOL = "httpx"
    TOOL_VERSION = "1.6.1"
    PRODUCES = ("http.response",)

    def __init__(self):
        super().__init__()
        self._seen_urls: set[str] = set()

    def build_cmd(self, targets: List[str], cfg: BatchConfig, workdir: Path) -> Optional[List[str]]:
        tf = workdir / "targets.txt"; tf.write_text("\n".join(targets))
        threads = str(cfg.parameters.get("threads", 50))
        include_resp = cfg.parameters.get("include_response", True)
        include_chain = cfg.parameters.get("include_chain", False)

        argv = ["httpx", "-l", str(tf), "-json", "-silent", "-threads", threads]
        if include_resp:
            argv += ["-include-response"]
        if include_chain:
            argv += ["-include-chain"]
        return argv

    def _bump_unique(self, model: HttpResponse, hb: Heartbeat) -> None:
        key = model.url or f"{model.host}:{model.port or 80}{model.path or ''}"
        if key and key not in self._seen_urls:
            self._seen_urls.add(key)
            hb.metrics["processed_targets"] = len(self._seen_urls)

    def parse_tool_output(self, line: str, emit, hb: Heartbeat) -> None:
        s = line.strip()
        if not s:
            return
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            return

        # main response
        main = HttpResponse.from_httpx_json(obj)
        emit_event(emit, main)
        self._bump_unique(main, hb)

        # optional redirect chain
        chain = obj.get("chain") or []
        for hop in chain:
            hop_model = HttpResponse.from_httpx_json(hop)
            emit_event(emit, hop_model)
            self._bump_unique(hop_model, hb)

if __name__ == "__main__":
    import sys
    sys.exit(HttpxAdapter().run())
