from __future__ import annotations
from dataclasses import dataclass, asdict, is_dataclass, field
from typing import Any, Dict
from datetime import datetime
import base64

def _json_sanitize(v: Any) -> Any:
    # Convert datetimes → ISO, bytes → base64, drop Nones/empties recursively
    if is_dataclass(v):
        return _json_sanitize(asdict(v))
    if isinstance(v, dict):
        out = {}
        for k, val in v.items():
            sval = _json_sanitize(val)
            if sval in (None, "", [], {}):
                continue
            out[k] = sval
        return out
    if isinstance(v, (list, tuple, set)):
        cleaned = []
        for x in v:
            sx = _json_sanitize(x)
            if sx not in (None, "", [], {}):
                cleaned.append(sx)
        return cleaned
    if isinstance(v, (bytes, bytearray)):
        return base64.b64encode(v).decode("ascii")
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%dT%H:%M:%SZ")
    return v

@dataclass
class EventModel:
    event_type: str = field(init=False, default="")
    def to_payload(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("event_type", None)
        return _json_sanitize(data)

def emit_event(emit_fn, model: EventModel) -> None:
    emit_fn(model.event_type, model.to_payload())

@dataclass
class RelatedResource:
    """
    Minimal cross-reference to the primary subject of a finding, etc.

    Examples
    --------
    kind examples: ``dns.domain``, ``net.ip``, ``http.response``
    id   examples: ``sub.example.com``, ``203.0.113.7``, ``https://a.example.com/``
    """

    kind: str
    id: str
    rel: str = "subject"  # 'subject'|'evidence'|'related'


__all__ = ["EventModel", "RelatedResource", "emit_event"]
