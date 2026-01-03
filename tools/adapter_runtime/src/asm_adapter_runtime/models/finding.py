from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .base import EventModel
from .dns import DnsDomain
from .network import NetworkService


@dataclass
class Finding(EventModel):
    title: str
    severity: str
    description: str = ""
    categories: List[str] = field(default_factory=list)
    assets: List[Dict[str, str]] = field(default_factory=list)
    event_type: str = field(init=False, default="finding.v1")

    @staticmethod
    def from_network_service(service: NetworkService, *, title: str, severity: str, description: str = "") -> "Finding":
        asset = {"kind": "network.service", "id": f"{service.ip}:{service.port}/{service.protocol}"}
        if service.banner:
            asset["banner"] = service.banner
        return Finding(title=title, severity=severity, description=description, assets=[asset])

    @staticmethod
    def from_dns(domain: DnsDomain, *, title: str, severity: str, description: str = "") -> "Finding":
        asset = {"kind": "dns.domain", "id": domain.name}
        return Finding(title=title, severity=severity, description=description, assets=[asset])
