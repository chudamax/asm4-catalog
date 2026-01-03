from __future__ import annotations

import gzip
import json
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .io import download_to_path
from .utils import iso_now


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
    parameters: Dict[str, object] = field(default_factory=dict)
    resources: List[ResourceSpec] = field(default_factory=list)
    resources_dir: Optional[Path] = None

    @staticmethod
    def from_manifest_doc(doc: Optional[dict]) -> "BatchConfig":
        doc = doc or {}
        params = doc.get("parameters") or {}
        resources: List[ResourceSpec] = []
        for item in doc.get("resources", []) or []:
            resources.append(
                ResourceSpec(
                    name=item.get("name", ""),
                    url=item.get("url", ""),
                    sha256=item.get("sha256"),
                    filename=item.get("filename"),
                    extract=bool(item.get("extract")),
                )
            )
        return BatchConfig(
            tool=str(doc.get("tool") or ""),
            tool_version=str(doc.get("tool_version") or ""),
            parameters=params,
            resources=resources,
        )


class EventWriter:
    """Serialize events into a gzipped JSON lines file."""

    def __init__(self, gz_path: Path, context: Dict[str, str]) -> None:
        self.gz_path = gz_path
        self.context = dict(context)
        self.count = 0
        self._raw = gz_path.open("wb")
        self._gzip = gzip.GzipFile(fileobj=self._raw, mode="wb")

    def emit(self, event_type: str, payload: dict) -> None:
        envelope = {
            "event_type": event_type,
            "timestamp": iso_now(),
            "payload": payload,
            **self.context,
        }
        data = json.dumps(envelope, separators=(",", ":")) + "\n"
        self._gzip.write(data.encode("utf-8"))
        self.count += 1

    def close(self) -> None:
        try:
            self._gzip.close()
        finally:
            self._raw.close()


def extract_resource(archive: Path, destination: Path) -> None:
    low = archive.name.lower()
    if low.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(destination)
    elif low.endswith((".tar", ".tgz", ".tar.gz", ".tar.bz2")):
        mode = "r"
        if low.endswith(".tgz") or low.endswith(".tar.gz"):
            mode = "r:gz"
        elif low.endswith(".tar.bz2"):
            mode = "r:bz2"
        with tarfile.open(archive, mode) as tf:
            tf.extractall(destination)


def materialize_resource(spec: ResourceSpec, destination_dir: Path) -> Path:
    filename = spec.filename or Path(spec.url.split("?")[0]).name or spec.name
    dest = destination_dir / filename
    download_to_path(spec.url, dest)
    if spec.extract:
        extract_resource(dest, destination_dir)
    return dest
