from __future__ import annotations

import os, io, json, gzip, time, hashlib, threading, tempfile, shutil, subprocess, sys, tarfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Callable, Optional, Any, Dict, List, Tuple
from urllib.parse import urlparse

import requests

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
def iso_now() -> str: return datetime.now(timezone.utc).strftime(ISO_FMT)
def _env(name: str, default: str="") -> str: return os.getenv(name) or default


def _is_file_url(url: Optional[str]) -> bool:
    return bool(url and url.startswith("file://"))


def _file_path_from_url(url: str) -> Path:
    parsed = urlparse(url)
    path = parsed.path
    if parsed.netloc and not path.startswith("/"):
        path = f"/{parsed.netloc}{path}"  # file://localhost/tmp -> /localhost/tmp
    return Path(path)

def _post(url: Optional[str], payload: dict, timeout: int = 15) -> None:
    if not url: return
    try: requests.post(url, json=payload, timeout=timeout)
    except Exception: pass

def _http_get_text(url: str, timeout: int = 60) -> str:
    if _is_file_url(url):
        return _file_path_from_url(url).read_text(encoding="utf-8")
    r = requests.get(url, timeout=timeout); r.raise_for_status(); return r.text


def _http_get_json(url: str, timeout: int = 60) -> dict:
    if _is_file_url(url):
        import json as _json

        with _file_path_from_url(url).open("r", encoding="utf-8") as fp:
            return _json.load(fp)
    r = requests.get(url, timeout=timeout); r.raise_for_status(); return r.json()


def _http_get_stream(url: str, timeout: int = 600, chunk: int = 1 << 20) -> Iterable[bytes]:
    if _is_file_url(url):
        with _file_path_from_url(url).open("rb") as fp:
            while True:
                part = fp.read(chunk)
                if not part:
                    break
                yield part
        return
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        for part in r.iter_content(chunk_size=chunk):
            if part:
                yield part


def _http_put_stream(url: str, fp, content_type: str, timeout: int = 600) -> None:
    headers = {"Content-Type": content_type}; fp.seek(0)
    if _is_file_url(url):
        dst = _file_path_from_url(url)
        with dst.open("wb") as out:
            shutil.copyfileobj(fp, out)
        return
    r = requests.put(url, data=fp, headers=headers, timeout=timeout); r.raise_for_status()

def _sha256_file(path: Path, chunk: int = 1<<20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""): h.update(b)
    return h.hexdigest()

@dataclass
class ResourceSpec:
    name: str
    url: str
    sha256: Optional[str] = None
    filename: Optional[str] = None
    extract: bool = False

@dataclass
class BatchConfig:
    tool: str
    tool_version: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    resources: List[ResourceSpec] = field(default_factory=list)
    @staticmethod
    def from_manifest_doc(doc: dict) -> "BatchConfig":
        params = (doc or {}).get("parameters") or {}
        res: List[ResourceSpec] = []
        for r in (doc or {}).get("resources", []) or []:
            res.append(ResourceSpec(
                name=r.get("name"), url=r.get("url"), sha256=r.get("sha256"),
                filename=r.get("filename"), extract=bool(r.get("extract", False))
            ))
        return BatchConfig(
            tool=(doc or {}).get("tool",""), tool_version=str((doc or {}).get("tool_version","")),
            parameters=params, resources=res
        )

class EventWriter:
    def __init__(self, gz_path: Path, ctx: Dict[str, str]):
        self.gz_path = gz_path; self.count = 0; self.ctx = ctx
        self._fp = open(gz_path, "wb")
        self._gz = gzip.GzipFile(fileobj=self._fp, mode="wb")
    def emit(self, event_type: str, payload: dict) -> None:
        env = {"tool": self.ctx["tool"], "tool_version": self.ctx["tool_version"],
               "run_id": self.ctx["run_id"], "batch_id": self.ctx["batch_id"],
               "event_type": event_type, "timestamp": iso_now(), "payload": payload}
        if self.ctx.get("tool_image_digest"):
            env["tool_image_digest"] = self.ctx["tool_image_digest"]
        self._gz.write((json.dumps(env, separators=(",",":"))+"\n").encode("utf-8"))
        self.count += 1
    def close(self) -> None:
        try: self._gz.close()
        finally: self._fp.close()

class Heartbeat:
    def __init__(self, signal_url: Optional[str], base: dict, interval_s: int = 30):
        self.url = signal_url; self.base = dict(base); self.interval_s = max(5, interval_s)
        self._stop = threading.Event()
        self.metrics = {"processed_targets": 0, "emitted_docs": 0, "phase": "start"}
    def start(self):
        t = threading.Thread(target=self._run, daemon=True); t.start(); return t
    def _run(self):
        while not self._stop.is_set():
            self._send(); self._stop.wait(self.interval_s)
    def _send(self):
        p = dict(self.base); p.update({"kind":"progress@v1", **self.metrics, "at": iso_now()})
        _post(self.url, p, timeout=10)
    def stop(self):
        self._stop.set(); self._send()

class BaseAdapter:
    """
    Implement exactly ONE of:
      - generate(targets, cfg, emit, hb)         # produce EventModel objects or raw payloads and call emit(...)
      - build_cmd(...), parse_tool_output(...)   # run a CLI and parse stdout to EventModels or payloads
    """
    TOOL: str = ""; TOOL_VERSION: str = ""
    PRODUCES: Tuple[str,...] = tuple()
    HEARTBEAT_S: int = int(os.getenv("HEARTBEAT_SECONDS") or "30")

    def generate(self, targets: List[str], cfg: BatchConfig, emit, hb: Heartbeat) -> int:
        raise NotImplementedError
    def build_cmd(self, targets: List[str], cfg: BatchConfig, workdir: Path) -> Optional[List[str]]:
        return None
    def parse_tool_output(self, line: str, emit, hb: Heartbeat) -> None:
        raise NotImplementedError

    def run(self) -> int:
        tenant_id  = _env("TENANT_ID"); run_id = _env("RUN_ID"); batch_id = _env("BATCH_ID")
        inputs_url = os.getenv("INPUTS_URL"); resman_url = os.getenv("RESOURCES_MANIFEST_URL")
        signal_url = os.getenv("SIGNAL_URL"); output_url = os.getenv("OUTPUT_URL")
        ocs_prefix = _env("OCS_PREFIX"); tool = self.TOOL or _env("TOOL"); tool_version = self.TOOL_VERSION or _env("TOOL_VERSION")
        if not inputs_url: print("FATAL: missing INPUTS_URL", file=sys.stderr); return 2

        workdir = Path(tempfile.mkdtemp(prefix=f"asm-batch-{batch_id or 'local'}-"))
        resources_dir = workdir / "resources"; resources_dir.mkdir(parents=True, exist_ok=True)
        events_path = workdir / "events.jsonl.gz"

        try:
            raw_inputs = _http_get_text(inputs_url, timeout=180)
            targets = [ln.strip() for ln in raw_inputs.splitlines() if ln.strip()]

            cfg = BatchConfig(tool=tool, tool_version=tool_version)
            if resman_url:
                try: cfg = BatchConfig.from_manifest_doc(_http_get_json(resman_url, timeout=180))
                except Exception as e: print(f"WARN manifest: {e}", file=sys.stderr)
            cfg.tool = cfg.tool or tool; cfg.tool_version = cfg.tool_version or tool_version

            # fetch resources (verify checksum; optionally extract)
            for r in cfg.resources:
                dst_name = r.filename or Path(r.url.split("?")[0]).name or r.name
                dst = resources_dir / dst_name
                h = hashlib.sha256()
                with open(dst, "wb") as f:
                    for chunk in _http_get_stream(r.url):
                        f.write(chunk); h.update(chunk)
                if r.sha256 and h.hexdigest() != r.sha256:
                    raise RuntimeError(f"sha256 mismatch for resource {r.name}")
                if r.extract:
                    low = dst.name.lower()
                    if low.endswith(".zip"):
                        import zipfile; zipfile.ZipFile(dst).extractall(resources_dir)
                    elif low.endswith((".tar",".tgz",".tar.gz")):
                        mode = "r:gz" if low.endswith((".tgz",".tar.gz")) else "r"
                        tarfile.open(dst, mode).extractall(resources_dir)

            tool_image_digest = os.getenv("TOOL_IMAGE_DIGEST") or None
            writer = EventWriter(events_path, ctx={"tool": cfg.tool, "tool_version": cfg.tool_version,
                                                   "run_id": run_id, "batch_id": batch_id,
                                                   "tool_image_digest": tool_image_digest})
            hb = Heartbeat(signal_url, base={"tenant_id":tenant_id,"run_id":run_id,"batch_id":batch_id,
                                             "tool":cfg.tool,"tool_version":cfg.tool_version}, interval_s=self.HEARTBEAT_S)
            hb.start()

            def emit(event_type: str, payload: dict):
                if self.PRODUCES and event_type not in self.PRODUCES: return
                writer.emit(event_type, payload); hb.metrics["emitted_docs"] = writer.count

            exit_code = 0
            try:
                argv = self.build_cmd(targets, cfg, workdir)
                if argv:
                    hb.metrics.update({"phase":"exec", "processed_targets":0})
                    proc = subprocess.Popen(argv, cwd=str(workdir), stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
                    for line in proc.stdout:
                        try: self.parse_tool_output(line, emit, hb)
                        except Exception: pass
                    proc.wait(); exit_code = proc.returncode or 0
                else:
                    hb.metrics.update({"phase":"generate", "processed_targets":len(targets)})
                    before = writer.count
                    self.generate(targets, cfg, emit, hb)
                    exit_code = 0 if writer.count >= before else 2
            finally:
                writer.close(); hb.metrics["phase"] = "finalize"; hb.stop()

            sha = _sha256_file(events_path)
            if output_url:
                with open(events_path, "rb") as f:
                    _http_put_stream(output_url, f, content_type="application/gzip")

            payload = {
                "kind":"results_ready@v1","tenant_id":tenant_id,"run_id":run_id,"batch_id":batch_id,
                "tool":cfg.tool,"tool_version":cfg.tool_version,"doc_count":writer.count,
                "events_blob": f"{ocs_prefix}events.jsonl.gz" if ocs_prefix else "events.jsonl.gz",
                "events_sha256": sha,"created_at": iso_now()
            }
            if tool_image_digest: payload["tool_image_digest"] = tool_image_digest
            _post(signal_url, payload, timeout=30)
            return exit_code
        except Exception as e:
            _post(signal_url, {"kind":"progress@v1","tenant_id":tenant_id,"run_id":run_id,"batch_id":batch_id,
                               "tool":tool,"tool_version":tool_version,"phase":"error","error":str(e),"at": iso_now()}, timeout=10)
            print(f"FATAL: {e}", file=sys.stderr); return 1
        finally:
            preserve = os.getenv("ADAPTER_PRESERVE_WORKDIR")
            if not preserve or preserve.lower() not in {"1", "true", "yes"}:
                shutil.rmtree(workdir, ignore_errors=True)
