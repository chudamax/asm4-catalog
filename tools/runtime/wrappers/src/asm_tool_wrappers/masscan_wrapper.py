from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from asm_adapter_runtime.models.network import NetworkService
from asm_tool_wrappers.base_wrapper import BaseWrapper, EmitFn

class MasscanWrapper(BaseWrapper):
    name = "masscan"
    version = "1"
    produces = ("network.service",)

    def __init__(self) -> None:
        self._jsonl: Optional[Path] = None

    def build_cmd(self, targets: List[str], params: Dict[str, Any], workdir: Path) -> Optional[List[str]]:
        if not targets:
            return None

        target_file = workdir / "targets.txt"
        target_file.write_text("\n".join(targets) + "\n", encoding="utf-8")

        self._jsonl = workdir / "masscan.jsonl"

        ports = _normalize_ports(params.get("ports") or params.get("masscan_ports")) or "1-1024"
        rate = str(params.get("rate") or params.get("masscan_rate") or "1000")
        interface = params.get("masscan_interface") or params.get("interface")
        extra_args = params.get("extra_args") or params.get("masscan_extra_args")

        cmd: List[str] = [
            "masscan",
            "-p",
            ports,
            "--rate",
            str(rate),
            "--open",
            "-oJ",
            str(self._jsonl),
            "-iL",
            str(target_file),
        ]

        if interface:
            cmd.extend(["--interface", str(interface)])

        for shard_flag in ("shards", "shard", "masscan_shards", "masscan_shard"):
            if shard_flag in params:
                value = params[shard_flag]
                if shard_flag.endswith("s") and isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 2:
                    cmd.extend(["--shards", str(value[0]), str(value[1])])
                else:
                    cmd.extend(["--shard", str(value)])
                break

        exclude = params.get("exclude") or params.get("exclude_file") or params.get("masscan_exclude")
        if exclude:
            cmd.extend(["--excludefile", str(exclude)])

        if params.get("banners") or params.get("masscan_banners"):
            cmd.append("--banners")

        if isinstance(extra_args, Sequence) and not isinstance(extra_args, (str, bytes)):
            cmd.extend(str(arg) for arg in extra_args)
        elif isinstance(extra_args, (str, bytes)) and str(extra_args).strip():
            cmd.append(str(extra_args).strip())

        return cmd

    def stream(self, line: str, emit: EmitFn) -> None:
        """Masscan does not emit useful structured stdout; ignore lines."""
        return None

    def postprocess_files(self, workdir: Path, emit: EmitFn) -> None:
        if not self._jsonl or not self._jsonl.exists():
            return

        text = self._jsonl.read_text(encoding="utf-8").strip()
        if not text:
            return

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            for raw_line in text.splitlines():
                raw_line = raw_line.strip()
                if not raw_line or raw_line.startswith("#"):
                    continue
                _emit_masscan_obj(raw_line, emit)
            return

        if isinstance(data, list):
            for obj in data:
                _emit_masscan_obj(obj, emit)

    def artifacts(self, workdir: Path) -> List[Tuple[Path, str]]:
        if self._jsonl and self._jsonl.exists():
            return [(self._jsonl, "application/json")]
        return []

    def run(
        self,
        *targets: Any,
        params: Optional[Dict[str, Any]] = None,
        ip: Optional[str] = None,
        verbose: bool = True,
        **extra_params: Any,
    ) -> List[NetworkService]:
        """Execute masscan directly and collect discovered services.

        Parameters mirror :meth:`build_cmd` for convenience and make it possible to
        run the wrapper from an interactive shell, e.g.::

            MasscanWrapper().run(ip="1.1.1.1", ports=[80, 443])

        Args:
            *targets: Positional targets to scan. Each target can be a string or an
                iterable of strings. Empty values are ignored.
            params: Optional dictionary of masscan parameters.
            ip: Convenience keyword for a single target IP/hostname.
            verbose: When ``True`` (default) prints the command and stderr output.
            **extra_params: Additional keyword parameters forwarded to
                :meth:`build_cmd` (for example ``ports`` or ``rate``).

        Returns:
            A list of :class:`NetworkService` instances detected by the scan.
        """

        all_targets = _flatten_targets(targets)
        if ip:
            _append_target(all_targets, ip)

        if not all_targets:
            return []

        parameters: Dict[str, Any] = {}
        if params:
            parameters.update(params)
        if extra_params:
            parameters.update(extra_params)

        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)
            cmd = self.build_cmd(all_targets, parameters, workdir)
            if not cmd:
                return []

            if verbose:
                print("Running masscan:", " ".join(cmd), file=sys.stderr)

            try:
                proc = subprocess.run(
                    cmd,
                    cwd=workdir,
                    check=False,
                    capture_output=True,
                    text=True,
                )
            except FileNotFoundError as exc:  # pragma: no cover - environment specific
                raise RuntimeError(
                    "masscan executable not found. Ensure it is installed and on PATH."
                ) from exc

            if verbose and proc.stderr:
                sys.stderr.write(proc.stderr)

            services: List[NetworkService] = []

            def collect(event: NetworkService) -> None:
                services.append(event)

            if proc.stdout:
                for line in proc.stdout.splitlines():
                    stripped = line.strip()
                    if stripped:
                        self.stream(stripped, collect)

            self.postprocess_files(workdir, collect)

            if verbose and proc.returncode:
                print(
                    f"masscan exited with status {proc.returncode}",
                    file=sys.stderr,
                )

        return services


def _normalize_ports(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        parts = [str(v).strip() for v in value if str(v).strip()]
        return ",".join(parts) if parts else None
    text = str(value).strip()
    return text or None


def _emit_masscan_obj(obj: Any, emit: EmitFn) -> None:
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            return
    if not isinstance(obj, dict):
        return
    ip = obj.get("ip")
    if not ip:
        return
    ports = obj.get("ports") or []
    for port_info in ports:
        if port_info.get("status") and port_info.get("status") != "open":
            continue
        try:
            port = int(port_info.get("port", 0))
        except (TypeError, ValueError):
            port = 0
        if port <= 0:
            continue
        emit(
            NetworkService(
                ip=ip,
                port=port,
                protocol=str(port_info.get("proto", "tcp")),
                banner=port_info.get("service") or port_info.get("banner"),
            )
        )


def _flatten_targets(targets: Iterable[Any]) -> List[str]:
    flattened: List[str] = []
    for target in targets:
        if isinstance(target, Iterable) and not isinstance(target, (str, bytes)):
            for sub in target:
                _append_target(flattened, sub)
        else:
            _append_target(flattened, target)
    return flattened


def _append_target(collection: List[str], value: Any) -> None:
    if value is None:
        return
    text = str(value).strip()
    if text:
        collection.append(text)


def main() -> None:  # pragma: no cover - development helper
    import argparse

    parser = argparse.ArgumentParser(description="Run the Masscan wrapper manually")
    parser.add_argument(
        "targets",
        nargs="*",
        help="Targets to scan (IP, CIDR, or hostname).",
    )
    parser.add_argument("--ip", help="Convenience option for a single IP/hostname")
    parser.add_argument(
        "--ports",
        help="Ports to scan (supports ranges and comma-separated lists)",
    )
    parser.add_argument("--rate", type=int, help="Packets per second rate for masscan")
    parser.add_argument(
        "--interface",
        dest="interface",
        help="Network interface for masscan to use",
    )
    parser.add_argument(
        "--extra-arg",
        dest="extra_args",
        action="append",
        help="Additional raw arguments to pass through to masscan",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress informational output",
    )

    args = parser.parse_args()

    wrapper = MasscanWrapper()
    params: Dict[str, Any] = {}

    if args.ports:
        params["ports"] = args.ports
    if args.rate is not None:
        params["rate"] = args.rate
    if args.interface:
        params["interface"] = args.interface
    if args.extra_args:
        params["extra_args"] = args.extra_args

    try:
        services = wrapper.run(
            *args.targets,
            params=params,
            ip=args.ip,
            verbose=not args.quiet,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    if not services and not args.quiet:
        print("No services discovered", file=sys.stderr)

    for svc in services:
        payload = {"event_type": svc.event_type, **svc.to_payload()}
        print(json.dumps(payload))


if __name__ == "__main__":  # pragma: no cover - module entry point
    main()
