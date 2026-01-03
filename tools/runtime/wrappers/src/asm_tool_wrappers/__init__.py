"""Wrappers around CLI tools that emit canonical ASM events."""

from .base_wrapper import BaseWrapper, EmitFn
from .masscan_wrapper import MasscanWrapper

__all__ = ["BaseWrapper", "EmitFn", "MasscanWrapper"]
