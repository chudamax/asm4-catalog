from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .base import EventModel


def _derive_scheme(url: Optional[str], fallback: Optional[str]) -> Optional[str]:
    if url:
        parsed = urlparse(url)
        if parsed.scheme:
            return parsed.scheme.lower()
    return fallback.lower() if isinstance(fallback, str) and fallback else fallback


@dataclass
class HttpResponse(EventModel):
    """Represents the subset of ``httpx`` response data we care about."""

    url: str
    host: Optional[str] = None
    ip: Optional[str] = None
    port: Optional[int] = None
    scheme: Optional[str] = None
    method: str = "GET"
    status_code: Optional[int] = None
    title: Optional[str] = None
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    webserver: Optional[str] = None
    response_time: Optional[float] = None
    words: Optional[int] = None
    lines: Optional[int] = None
    body_mmh3_hash: Optional[str] = None
    headers_mmh3_hash: Optional[str] = None
    favicon_mmh3_hash: Optional[str] = None
    headers: Dict[str, Any] = field(default_factory=dict)
    target: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)
    event_type: str = "http.response"

    @staticmethod
    def from_httpx_json(doc: Dict[str, Any]) -> "HttpResponse":
        hash_info = doc.get("hash") or {}

        body_hash = hash_info.get("body_mmh3")
        headers_hash = hash_info.get("header_mmh3")

        response_time = doc.get("response_time") or doc.get("time")
        if isinstance(response_time, str):
            try:
                response_time = float(response_time)
            except ValueError:  # pragma: no cover - depends on tool output
                response_time = None

        final_url = doc.get("final_url") or doc.get("url") or doc.get("input") or ""

        scheme = _derive_scheme(final_url, doc.get("scheme")) or "http"

        return HttpResponse(
            url=final_url,
            host=doc.get("host"),
            ip=doc.get("ip"),
            port=doc.get("port"),
            scheme=scheme,
            method=(doc.get("method") or "GET").upper(),
            status_code=doc.get("status_code"),
            title=doc.get("title"),
            content_type=doc.get("content_type"),
            content_length=doc.get("content_length"),
            webserver=doc.get("webserver"),
            response_time=response_time,
            words=doc.get("words"),
            lines=doc.get("lines"),
            body_mmh3_hash=str(body_hash) if body_hash is not None else None,
            headers_mmh3_hash=str(headers_hash) if headers_hash is not None else None,
            favicon_mmh3_hash=str(doc.get("favicon")) if doc.get("favicon") is not None else None,
            headers=doc.get("response_headers") or doc.get("header") or {},
            target=doc.get("input"),
            raw=doc,
        )
