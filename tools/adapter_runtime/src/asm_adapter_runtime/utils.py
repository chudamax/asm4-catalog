from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def iso_now() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""

    return datetime.now(timezone.utc).strftime(ISO_FORMAT)


def env_str(name: str, default: str | None = None) -> str | None:
    """Fetch an environment variable, falling back to ``default`` if unset."""

    value = os.getenv(name)
    return value if value is not None else default


def env_flag(name: str, default: bool = False) -> bool:
    """Return True when the named environment variable is truthy."""

    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def ensure_dir(path: Path) -> Path:
    """Create ``path`` (recursively) if it does not exist."""

    path.mkdir(parents=True, exist_ok=True)
    return path


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Compute the SHA-256 hash for ``path``."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_rmtree(path: Path) -> None:
    """Best-effort removal of ``path`` while ignoring most errors."""

    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        return


def should_preserve_workdir() -> bool:
    return env_flag("ADAPTER_PRESERVE_WORKDIR", False)


def coalesce(value: Optional[str], fallback: str) -> str:
    return value if value else fallback
