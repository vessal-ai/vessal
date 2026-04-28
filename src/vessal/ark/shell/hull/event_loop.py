"""event_loop.py — Hull event loop: drives the Agent sleep/wake lifecycle and frame execution."""
from __future__ import annotations

import asyncio
import logging
import queue as queue_mod
import time as _time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from vessal.ark.util.logging import Tracer

if TYPE_CHECKING:
    from vessal.ark.shell.hull.cell import Cell

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# FrameHooks
# ─────────────────────────────────────────────


@dataclass
class FrameHooks:
    """Callback interface between EventLoop and Hull, allowing EventLoop to avoid depending on Hull directly.

    Attributes:
        before_frame: Called before each frame; Hull uses it to rewrite runtime-owned vars.
        snapshot: Called after each wake cycle ends; Hull uses it to save a snapshot.
    """

    before_frame: Callable[[], None] | None = None
    """Called before each frame. Hull uses it to re-fill runtime-owned variables."""

    after_frame: Callable[[], None] | None = None
    """Post-frame hook; reserved for future Hull-owned work after each frame."""

    snapshot: Callable[[], None] | None = None
    """Called after each wake cycle ends. Hull uses it to save a snapshot."""


# ─────────────────────────────────────────────
# EventLoop
# ─────────────────────────────────────────────


class EventLoop:
    """Agent event loop: wait for event → inject into namespace → frame loop → snapshot → wait again.

    Attributes:
        _cell: Cell instance — the target for frame execution.
        _queue: Event queue (stdlib queue.Queue); Shell pushes wake events through this.
        _max_frames: Maximum number of frames per wake cycle.
        _tracer: Tracer instance for writing execution trace logs.
        _alive: Event loop running flag; set to False by stop().
        _hooks: FrameHooks callback set, injected by Hull.
    """

    def __init__(
        self,
        cell: "Cell",
        event_queue: "queue_mod.Queue | None" = None,
        max_frames_per_wake: int = 100,
        tracer: Tracer | None = None,
        hooks: "FrameHooks | None" = None,
    ):
        self._cell = cell
        self._queue: queue_mod.Queue = event_queue or queue_mod.Queue()
        self._max_frames = max_frames_per_wake
        self._tracer = tracer or Tracer("", enabled=False)
        self._alive = True
        self._hooks = hooks or FrameHooks()

    @property
    def event_queue(self) -> queue_mod.Queue:
        """Shell pushes events to Hull via this queue. Thread-safe."""
        return self._queue

    def inject_wake(self, event: dict) -> None:
        """Record wake reason on _system Skill and clear _sleeping.

        Args:
            event: Event dict; must contain a reason key; defaults to "heartbeat" if absent.
        """
        reason = event.get("reason", "heartbeat")
        system_skill = self._cell.G.get("_system")
        if system_skill is not None:
            system_skill.wake(reason)

    async def run_forever(self) -> None:
        """Main event loop. Runs inside asyncio; frame execution happens in a thread."""
        while self._alive:
            try:
                event = await asyncio.to_thread(self._queue.get)
            except Exception:
                break

            self.inject_wake(event)
            await asyncio.to_thread(self._run_wake_cycle)

    async def step(self) -> None:
        """Execute one wake cycle and return.

        Waits for one event, runs the frame loop until idle, saves a snapshot, then returns.
        Used for `vessal run --goal "..."` single-run mode.
        """
        try:
            event = await asyncio.to_thread(self._queue.get)
        except Exception:
            return

        self.inject_wake(event)
        await asyncio.to_thread(self._run_wake_cycle)

    def _run_wake_cycle(self) -> None:
        """One wake cycle: initialize logging → frame loop → close logging. Runs in a dedicated thread."""
        from vessal.ark.util.logging import FrameLogger
        hooks = self._hooks
        frame_logger = None

        log_dir = self._tracer._log_dir
        if str(log_dir) not in ("", "."):
            Path(str(log_dir)).mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            self._tracer.init(timestamp)
            frame_logger = FrameLogger(log_dir)
            frame_logger.open()

        try:
            self._frame_loop(frame_logger)
        finally:
            if frame_logger is not None:
                frame_logger.close()
            if hooks.snapshot is not None:
                try:
                    hooks.snapshot()
                except Exception as e:
                    logger.warning("auto-snapshot failed: %s", e)

    def _frame_loop(self, frame_logger: Any = None) -> None:
        """Synchronous frame loop. Runs in a dedicated thread."""
        from vessal.ark.util.logging.console import print_frame_line
        hooks = self._hooks
        frame_count = 0

        system = self._cell.G.get("_system")
        while not (system._sleeping if system is not None else False):
            if self._max_frames > 0 and frame_count >= self._max_frames:
                logger.warning("max frames per wake reached (%d)", self._max_frames)
                break
            frame_count += 1

            if hooks.before_frame is not None:
                hooks.before_frame()

            self._cell.L["_memories"] = self._cell.L.get("_memories", [])
            result = self._cell.step(self._tracer)

            if result.protocol_error is None:
                fs = self._cell.L.get("_frame_stream")
                last_frame = fs.latest_hot_frame() if fs is not None else None
                if last_frame is not None:
                    if frame_logger is not None:
                        frame_logger.write_frame(last_frame)
                    print_frame_line(last_frame)
                if hooks.after_frame is not None:
                    hooks.after_frame()
            else:
                logger.error(
                    "protocol error at frame %d: %s",
                    self._cell.L.get("_frame", -1),
                    result.protocol_error,
                )
                if system is not None:
                    system.sleep()
                break

    def stop(self) -> None:
        """Request the event loop to stop."""
        self._alive = False
        try:
            self._queue.put_nowait({"reason": "shutdown"})
        except queue_mod.Full:
            pass
