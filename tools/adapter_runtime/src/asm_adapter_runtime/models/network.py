from __future__ import annotations

from dataclasses import dataclass

from .base import EventModel


@dataclass
class NetworkService(EventModel):
    event_type: str = "network.service"
    ip: str = ""
    port: int = 0
    protocol: str = "tcp"
    banner: str | None = None

    def to_payload(self) -> dict:
        return {
            "ip": self.ip,
            "port": self.port,
            "protocol": self.protocol,
            "banner": self.banner,
        }
