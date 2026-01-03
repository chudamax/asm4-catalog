from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

import requests

CHUNK_SIZE = 1 << 20


def is_file_url(url: Optional[str]) -> bool:
    return bool(url and url.startswith("file://"))


def _file_path_from_url(url: str) -> Path:
    parsed = urlparse(url)
    path = parsed.path
    if parsed.netloc and not path.startswith("/"):
        path = f"/{parsed.netloc}{path}"
    return Path(path)


def read_text(url: str, timeout: int = 180) -> str:
    if is_file_url(url):
        return _file_path_from_url(url).read_text(encoding="utf-8")
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def read_json(url: str, timeout: int = 180) -> dict:
    if is_file_url(url):
        with _file_path_from_url(url).open("r", encoding="utf-8") as handle:
            return json.load(handle)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def stream_bytes(url: str, timeout: int = 600, chunk_size: int = CHUNK_SIZE) -> Iterable[bytes]:
    if is_file_url(url):
        with _file_path_from_url(url).open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        return
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                yield chunk


def download_to_path(url: str, destination: Path, timeout: int = 600) -> None:
    with destination.open("wb") as handle:
        for chunk in stream_bytes(url, timeout=timeout):
            handle.write(chunk)


def upload_file(url: str, source: Path, content_type: str = "application/gzip", timeout: int = 600) -> None:
    if is_file_url(url):
        dst = _file_path_from_url(url)
        dst.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as src, dst.open("wb") as dst_handle:
            shutil.copyfileobj(src, dst_handle)
        return
    headers = {"Content-Type": content_type}
    with source.open("rb") as src:
        response = requests.put(url, data=src, headers=headers, timeout=timeout)
        response.raise_for_status()


def post_json(url: Optional[str], payload: dict, timeout: int = 15) -> None:
    if not url:
        return
    try:
        requests.post(url, json=payload, timeout=timeout)
    except Exception:
        # Signals should never crash the adapter runtime.
        return
