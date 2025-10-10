from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Tuple


@dataclass
class EventModel:
    """Simple base class for strongly-typed tool events."""

    event_type: str

    def to_payload(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("event_type", None)
        return data

    def to_event(self) -> Tuple[str, Dict[str, Any]]:
        return self.event_type, self.to_payload()


def emit_event(event: EventModel, emit) -> None:
    """Helper that normalises models before invoking ``emit``."""

    if isinstance(event, EventModel):
        event_type, payload = event.to_event()
        emit(event_type, payload)
    else:  # pragma: no cover - defensive fallback
        raise TypeError("emit_event expects an EventModel instance")
