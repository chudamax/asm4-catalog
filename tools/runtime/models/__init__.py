"""Typed event helpers shared by adapters."""
from .base import EventModel, emit_event
from .dns import DnsDomain
from .http import HttpResponse

__all__ = ["EventModel", "emit_event", "DnsDomain", "HttpResponse"]
