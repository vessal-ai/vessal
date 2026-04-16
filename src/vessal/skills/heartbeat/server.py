"""heartbeat server — heartbeat timer.

Convention-based server: exports start(hull_api) and stop().
Hull auto-discovers and manages the lifecycle.

Uses instance pattern (not module globals) to ensure safe test isolation.
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vessal.ark.shell.hull.hull_api import HullApi

_instance: "_HeartbeatServer | None" = None


class _HeartbeatServer:
    def __init__(self, hull_api: "HullApi", interval: float):
        self._hull_api = hull_api
        self._interval = interval
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="heartbeat"
        )

    def _loop(self):
        while not self._stop_event.is_set():
            if self._stop_event.wait(timeout=self._interval):
                break
            self._hull_api.wake("heartbeat")

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=5)


def start(hull_api: "HullApi", *, heartbeat: float = 1800.0) -> None:
    """Start the heartbeat. Interval is passed by Hull from hull.toml [hull].heartbeat."""
    global _instance
    if _instance is not None:
        stop()
    _instance = _HeartbeatServer(hull_api, heartbeat)
    _instance.start()


def stop() -> None:
    """Stop the heartbeat."""
    global _instance
    if _instance is not None:
        _instance.stop()
        _instance = None
