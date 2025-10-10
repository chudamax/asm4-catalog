from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from .base import EventModel
from urllib.parse import urlparse, ParseResult

def _parse_url(url: Optional[str], scheme: Optional[str], host: Optional[str], path: Optional[str]) -> Tuple[str,str,Optional[str],Optional[str]]:
    """
    Returns (scheme, host, norm_path, norm_query).
    If `url` present, prefer it; otherwise compose from fields.
    """
    if url:
        u: ParseResult = urlparse(url)
        sch = (u.scheme or scheme or "").lower()
        h = (u.hostname or host or "") or None
        p = u.path or path or "/"
        q = u.query or None
        return sch, h, p if p else "/", q
    # fallback
    return (scheme or "http").lower(), host or None, (path or "/") or "/", None

@dataclass
class HttpResource(EventModel):
    """
    Mirrors InvHTTPResource identity/fields, plus parent HttpService link.

      unique: (http_service, method, path, query)

    Parent link is flattened so the ingestor can resolve HttpService first:
      (ip, port, transport, scheme, host)
    """
    # Parent HttpService identity
    ip: Optional[str] = None
    port: Optional[int] = None
    transport: str = "tcp"
    scheme: str = "http"
    host: Optional[str] = None

    # Resource identity
    method: str = "GET"
    path: str = "/"
    query: Optional[str] = None

    # Templates / parametrics (optional)
    path_template: Optional[str] = None
    query_template: Optional[str] = None
    is_parametric: bool = False
    route_signature: Optional[str] = None

    # Response snapshot
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    title: Optional[str] = None

    headers: Optional[Dict[str, Any]] = field(default_factory=dict)
    server: Optional[str] = None
    location: Optional[str] = None
    magic_type: Optional[str] = None
    jarm: Optional[str] = None

    words: Optional[int] = None
    lines: Optional[int] = None
    time: Optional[str] = None

    body_mmh3_hash: Optional[str] = None
    headers_mmh3_hash: Optional[str] = None
    favicon_mmh3_hash: Optional[str] = None

    labels: Dict[str, Any] = field(default_factory=dict)

    event_type: str = "http.resource"

    @staticmethod
    def from_httpx_json(o: Dict[str, Any]) -> "HttpResource":
        # Prefer final_url for accurate path/query, fall back to url/fields
        url = o.get("final_url") or o.get("url")
        sch, host, path, query = _parse_url(url, o.get("scheme"), o.get("host"), o.get("path"))

        # Hashes
        body_mmh3 = (o.get("hash") or {}).get("body_mmh3")
        headers_mmh3 = (o.get("hash") or {}).get("header_mmh3")
        favicon_mmh3 = o.get("favicon")

        return HttpResource(
            ip=o.get("ip") or o.get("host"),       # httpx sometimes sets 'ip'
            port=o.get("port"),
            transport="tcp",
            scheme=(sch or "http").lower(),
            host=host,

            method=(o.get("method") or "GET").upper(),
            path=path or "/",
            query=query,

            # templates/parametrics not derivable from httpx: leave defaults
            is_parametric=False,

            status_code=o.get("status_code"),
            content_type=o.get("content_type"),
            content_length=o.get("content_length"),
            title=o.get("title"),

            headers=o.get("header") or {},
            server=o.get("webserver"),
            location=o.get("location"),
            magic_type=None,  # derive via file magic if you attach bodies
            jarm=o.get("jarm"),

            words=o.get("words"),
            lines=o.get("lines"),
            time=o.get("time"),

            body_mmh3_hash=str(body_mmh3) if body_mmh3 is not None else None,
            headers_mmh3_hash=str(headers_mmh3) if headers_mmh3 is not None else None,
            favicon_mmh3_hash=str(favicon_mmh3) if favicon_mmh3 is not None else None,

            labels={},
        )

    def service_key(self) -> str:
        """Convenience for dedupe: scheme://(host|ip):port."""
        h = self.host or self.ip or ""
        return f"{self.scheme}://{h}:{self.port or 0}"