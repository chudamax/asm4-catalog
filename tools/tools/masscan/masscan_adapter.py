from __future__ import annotations

from asm_adapter_runtime import BatchConfig, Heartbeat, WrapperAdapter
from asm_adapter_runtime.base import EmitFn
from asm_tool_wrappers.masscan_wrapper import MasscanWrapper

class MasscanAdapter(WrapperAdapter):
    TOOL = "masscan"
    TOOL_VERSION = "1.3.2"
    PRODUCES = ("network.service",)

    def __init__(self) -> None:
        super().__init__(MasscanWrapper())

    def build_parameters(self, cfg: BatchConfig) -> dict:
        return cfg.parameters or {}
