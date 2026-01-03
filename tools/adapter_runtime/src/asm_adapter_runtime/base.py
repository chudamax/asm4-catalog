from __future__ import annotations

import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Sequence, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from asm_tool_wrappers.base_wrapper import BaseWrapper

from .envelope import BatchConfig, EventWriter, ResourceSpec, materialize_resource
from .io import read_json, read_text, upload_file
from .models.base import EventModel
from .signals import Heartbeat, emit_error, emit_results_ready
from .utils import (
    env_flag,
    env_str,
    ensure_dir,
    iso_now,
    safe_rmtree,
    sha256_file,
    should_preserve_workdir,
)

EmitFn = Callable[[EventModel], None]


@dataclass
class RuntimeSettings:
    inputs_url: str
    resources_manifest_url: Optional[str]
    output_url: Optional[str]
    signal_url: Optional[str]
    tenant_id: str
    run_id: str
    batch_id: str
    ocs_prefix: str
    tool_image_digest: Optional[str]
    tool: str
    tool_version: str
    heartbeat_seconds: int
    preserve_workdir: bool

    @classmethod
    def from_env(cls, default_tool: str, default_version: str) -> "RuntimeSettings":
        inputs_url = env_str("INPUTS_URL")
        if not inputs_url:
            raise RuntimeError("missing INPUTS_URL")

        return cls(
            inputs_url=inputs_url,
            resources_manifest_url=env_str("RESOURCES_MANIFEST_URL"),
            output_url=env_str("OUTPUT_URL"),
            signal_url=env_str("SIGNAL_URL"),
            tenant_id=env_str("TENANT_ID", "") or "",
            run_id=env_str("RUN_ID", "") or "",
            batch_id=env_str("BATCH_ID", "") or "",
            ocs_prefix=env_str("OCS_PREFIX", "") or "",
            tool_image_digest=env_str("TOOL_IMAGE_DIGEST") or None,
            tool=default_tool or env_str("TOOL", "") or "",
            tool_version=default_version or env_str("TOOL_VERSION", "") or "",
            heartbeat_seconds=int(env_str("HEARTBEAT_SECONDS", "30") or "30"),
            preserve_workdir=env_flag("ADAPTER_PRESERVE_WORKDIR", False),
        )


class BaseAdapter:
    TOOL: str = ""
    TOOL_VERSION: str = ""
    PRODUCES: Sequence[str] = ()

    def main(
        self,
        targets: List[str],
        cfg: BatchConfig,
        workdir: Path,
        emit: EmitFn,
        hb: Heartbeat,
    ) -> None:
        raise NotImplementedError

    def list_artifacts(self, workdir: Path) -> Sequence[Tuple[Path, str]]:
        return []

    def spawn_and_stream(
        self,
        argv: Sequence[str],
        on_line: Callable[[str], None],
        *,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        hb: Optional[Heartbeat] = None,
    ) -> int:
        if hb:
            hb.metrics["phase"] = "exec"
        process = subprocess.Popen(
            list(argv),
            cwd=str(cwd) if cwd else None,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        try:
            for raw_line in process.stdout:
                on_line(raw_line.rstrip("\n"))
        finally:
            process.wait()
        return process.returncode or 0

    def run(self, *, settings: Optional[RuntimeSettings] = None) -> int:
        try:
            runtime = settings or RuntimeSettings.from_env(self.TOOL, self.TOOL_VERSION)
        except Exception as exc:
            print(f"FATAL: {exc}", file=sys.stderr)
            return 2

        workdir = Path(tempfile.mkdtemp(prefix=f"asm-batch-{runtime.batch_id or 'local'}-"))
        resources_dir = ensure_dir(workdir / "resources")
        events_path = workdir / "events.jsonl.gz"

        def _handle_sigterm(signum, frame):  # pragma: no cover
            raise SystemExit(2)

        previous_handler = signal.signal(signal.SIGTERM, _handle_sigterm)

        signal_payload = self._build_signal_payload(runtime)
        hb = Heartbeat(runtime.signal_url, signal_payload, interval_s=runtime.heartbeat_seconds)
        writer: Optional[EventWriter] = None
        success = False
        resolved_tool = runtime.tool
        resolved_version = runtime.tool_version

        try:
            targets = self._load_targets(runtime.inputs_url)
            cfg = self._load_manifest(runtime.resources_manifest_url)
            cfg.tool = cfg.tool or runtime.tool
            cfg.tool_version = cfg.tool_version or runtime.tool_version
            cfg.resources_dir = resources_dir
            resolved_tool = cfg.tool
            resolved_version = cfg.tool_version

            for resource in cfg.resources:
                self._prepare_resource(resource, resources_dir)

            writer = EventWriter(events_path, context=self._build_event_context(runtime, resolved_tool, resolved_version))

            hb.metrics.update({"phase": "start", "processed_targets": len(targets), "emitted_docs": 0})
            hb.start()

            emit = self._build_emitter(writer, hb)

            hb.metrics["phase"] = "main"
            self.main(targets, cfg, workdir, emit, hb)
            hb.metrics["phase"] = "finalize"

            success = True
            return 0
        except SystemExit:
            raise
        except Exception as exc:  # pragma: no cover
            emit_error(runtime.signal_url, signal_payload, str(exc))
            print(f"FATAL: {exc}", file=sys.stderr)
            return 1
        finally:
            try:
                hb.stop()
            except Exception:
                pass

            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass

            signal.signal(signal.SIGTERM, previous_handler)

            if success and writer is not None:
                self._finalize_success(runtime, writer, events_path, resolved_tool, resolved_version)

            if not (runtime.preserve_workdir or should_preserve_workdir()):
                safe_rmtree(workdir)

    def _build_signal_payload(self, runtime: RuntimeSettings) -> Dict[str, str]:
        payload: Dict[str, str] = {
            "tenant_id": runtime.tenant_id,
            "run_id": runtime.run_id,
            "batch_id": runtime.batch_id,
            "tool": runtime.tool,
            "tool_version": runtime.tool_version,
        }
        if runtime.tool_image_digest:
            payload["tool_image_digest"] = runtime.tool_image_digest
        return payload

    def _build_event_context(self, runtime: RuntimeSettings, tool: str, tool_version: str) -> Dict[str, str]:
        context = {
            "tool": tool,
            "tool_version": tool_version,
            "run_id": runtime.run_id,
            "batch_id": runtime.batch_id,
        }
        if runtime.tool_image_digest:
            context["tool_image_digest"] = runtime.tool_image_digest
        return context

    def _build_emitter(self, writer: EventWriter, hb: Heartbeat) -> EmitFn:
        def emit(model: EventModel) -> None:
            if not isinstance(model, EventModel):  # pragma: no cover - guardrail
                raise TypeError("emit() expects an EventModel instance")
            if self.PRODUCES and model.event_type not in self.PRODUCES:
                return
            writer.emit(model.event_type, model.to_payload())
            hb.metrics["emitted_docs"] = writer.count

        return emit

    def _load_targets(self, inputs_url: str) -> List[str]:
        raw_inputs = read_text(inputs_url, timeout=180)
        return [line.strip() for line in raw_inputs.splitlines() if line.strip()]

    def _load_manifest(self, resman_url: Optional[str]) -> BatchConfig:
        cfg_doc: dict = {}
        if resman_url:
            try:
                cfg_doc = read_json(resman_url, timeout=180)
            except Exception as exc:
                print(f"WARN manifest: {exc}", file=sys.stderr)
        return BatchConfig.from_manifest_doc(cfg_doc)

    def _prepare_resource(self, spec: ResourceSpec, destination_dir: Path) -> Path:
        path = materialize_resource(spec, destination_dir)
        if spec.sha256:
            digest = sha256_file(path)
            if digest != spec.sha256:
                raise RuntimeError(f"sha256 mismatch for resource {spec.name or path.name}")
        return path

    def _finalize_success(
        self,
        runtime: RuntimeSettings,
        writer: EventWriter,
        events_path: Path,
        tool: str,
        tool_version: str,
    ) -> None:
        sha = sha256_file(events_path)
        if runtime.output_url:
            upload_file(runtime.output_url, events_path, content_type="application/gzip")

        results_payload: Dict[str, object] = {
            "tenant_id": runtime.tenant_id,
            "run_id": runtime.run_id,
            "batch_id": runtime.batch_id,
            "tool": tool,
            "tool_version": tool_version,
            "doc_count": writer.count,
            "events_blob": f"{runtime.ocs_prefix}events.jsonl.gz" if runtime.ocs_prefix else "events.jsonl.gz",
            "events_sha256": sha,
            "created_at": iso_now(),
        }
        if runtime.tool_image_digest:
            results_payload["tool_image_digest"] = runtime.tool_image_digest

        emit_results_ready(runtime.signal_url, results_payload)


class WrapperAdapter(BaseAdapter):
    """Base adapter for tools that expose a :class:`BaseWrapper`.

    Subclasses only need to provide ``wrapper`` and optionally override
    :meth:`build_parameters` if additional configuration transformation is needed.
    """

    wrapper: "BaseWrapper"

    def __init__(self, wrapper: "BaseWrapper") -> None:
        self.wrapper = wrapper
        self._artifacts: List[Tuple[Path, str]] = []

    def build_parameters(self, cfg: BatchConfig) -> Dict[str, object]:
        return cfg.parameters or {}

    def main(self, targets: List[str], cfg: BatchConfig, workdir: Path, emit: EmitFn, hb: Heartbeat) -> None:  # type: ignore[override]
        params = self.build_parameters(cfg)
        hb.metrics["processed_targets"] = len(targets)

        cmd = self.wrapper.build_cmd(targets, params, workdir)
        if cmd:
            exit_code = self.spawn_and_stream(cmd, lambda line: self.wrapper.stream(line, emit), cwd=workdir, hb=hb)
            hb.metrics["last_exit_code"] = exit_code

        self.wrapper.postprocess_files(workdir, emit)
        self._artifacts = list(self.wrapper.artifacts(workdir))

    def list_artifacts(self, workdir: Path) -> Sequence[Tuple[Path, str]]:  # type: ignore[override]
        return tuple(self._artifacts)
