from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
from .base import EventModel

DNS_KIND_VALUES = ("apex", "subdomain", "wildcard")

def _infer_root_kind_parent(name: str) -> Tuple[str, str, Optional[str]]:
    n = (name or "").strip().lstrip(".").lower()
    if n.startswith("*."):
        host = n[2:]
        parts = host.split(".")
        root = ".".join(parts[-2:]) if len(parts) >= 2 else host
        return root, "wildcard", root
    parts = n.split(".")
    if len(parts) <= 2:
        return n, "apex", None
    root = ".".join(parts[-2:])
    return root, "subdomain", root

@dataclass
class DnsDomain(EventModel):
    name: str
    root: str
    kind: str
    parent: Optional[str] = None
    event_type: str = "dns.domain"

    @staticmethod
    def from_name(name: str) -> "DnsDomain":
        root, kind, parent = _infer_root_kind_parent(name)
        if kind not in DNS_KIND_VALUES:
            kind = "subdomain"
        return DnsDomain(name=name.lower(), root=root, kind=kind, parent=parent)
