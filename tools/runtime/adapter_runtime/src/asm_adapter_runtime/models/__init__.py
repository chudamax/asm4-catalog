"""Typed event helpers shared by adapters."""

from .base import EventModel, emit_event
from .dns import DnsDomain
from .finding import Finding
from .http import HttpResponse
from .network import NetworkService

__all__ = [
    "EventModel",
    "emit_event",
    "DnsDomain",
    "Finding",
    "HttpResponse",
    "NetworkService",
]
