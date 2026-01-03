from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from asm_adapter_runtime.models.base import EventModel

EmitFn = Callable[[EventModel], None]


class BaseWrapper:
    """Common interface implemented by tool wrappers.

    Wrappers translate between raw tool output and :class:`EventModel` instances so
    adapters can remain lightweight. Subclasses only need to implement the pieces
    of the lifecycle that are relevant for the tool they wrap.
    """

    name: str = "wrapper"
    version: str = "dev"
    produces: tuple[str, ...] = ()

    def build_cmd(self, targets: List[str], params: Dict[str, Any], workdir: Path) -> Optional[List[str]]:
        """Return the command to execute or ``None`` if nothing should run."""

    def stream(self, line: str, emit: EmitFn) -> None:
        """Handle a single stdout/stderr line from the running tool."""

    def postprocess_files(self, workdir: Path, emit: EmitFn) -> None:
        """Handle any output files once the tool has finished running."""

    def artifacts(self, workdir: Path) -> List[Tuple[Path, str]]:
        """List output artifacts and their MIME types for upload."""
        return []
