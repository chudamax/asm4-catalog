from __future__ import annotations

import threading
from typing import Dict, Optional

from .io import post_json
from .utils import iso_now


class Heartbeat:
    """Background thread that periodically emits ``progress@v1`` signals."""

    def __init__(self, signal_url: Optional[str], base_payload: Dict[str, object], interval_s: int = 30) -> None:
        self.url = signal_url
        self.base_payload = dict(base_payload)
        self.interval_s = max(5, int(interval_s or 30))
        self.metrics: Dict[str, object] = {
            "phase": "init",
            "processed_targets": 0,
            "emitted_docs": 0,
        }
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if not self.url or self._thread:
            return
        thread = threading.Thread(target=self._run, name="asm-heartbeat", daemon=True)
        thread.start()
        self._thread = thread

    def _run(self) -> None:
        while not self._stop.wait(self.interval_s):
            self.send()

    def send(self) -> None:
        if not self.url:
            return
        payload = {**self.base_payload, **self.metrics, "kind": "progress@v1", "at": iso_now()}
        post_json(self.url, payload, timeout=10)

    def stop(self) -> None:
        self._stop.set()
        if self.url:
            self.send()


def emit_results_ready(
    signal_url: Optional[str],
    payload: Dict[str, object],
    timeout: int = 30,
) -> None:
    post_json(signal_url, {**payload, "kind": "results_ready@v1"}, timeout=timeout)


def emit_error(
    signal_url: Optional[str],
    base_payload: Dict[str, object],
    error: str,
    timeout: int = 10,
) -> None:
    if not signal_url:
        return
    payload = {**base_payload, "kind": "progress@v1", "phase": "error", "error": error, "at": iso_now()}
    post_json(signal_url, payload, timeout=timeout)
