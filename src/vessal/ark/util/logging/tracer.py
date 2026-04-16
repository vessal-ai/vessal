"""tracer.py — Records entry/exit times for Agent execution phases, writing to a .trace.log file."""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import IO, Generator


class Tracer:
    """Trace log manager.

    Records entry/exit times and durations for each key phase, writing to a separate .trace.log file.
    Enabled by default; controlled by hull.toml [cell].trace.
    """

    def __init__(self, log_dir: str, enabled: bool = True) -> None:
        """Initialize the Tracer.

        Args:
            log_dir: Log directory.
            enabled: Whether tracing is enabled, default True.
        """
        self._log_dir = Path(log_dir)
        self._enabled = enabled
        self._file: IO[str] | None = None
        self._start_times: dict[str, float] = {}

    def init(self, timestamp_prefix: str) -> Path | None:
        """Open the trace log file.

        Args:
            timestamp_prefix: Timestamp prefix, consistent with the other log files.

        Returns:
            Path to the log file, or None if tracing is not enabled.
        """
        if not self._enabled:
            return None
            
        self._log_dir.mkdir(parents=True, exist_ok=True)
        trace_path = self._log_dir / f"{timestamp_prefix}.trace.log"
        self._file = open(trace_path, "a", encoding="utf-8")
        return trace_path

    def log(self, frame: int, phase: str, event: str, duration_ms: int = -1, details: str = "") -> None:
        """Write one trace record.

        Args:
            frame: Current frame number.
            phase: Phase name, e.g. "cell.iteration", "signal.action_streak".
            event: Event type, e.g. "start", "end".
            duration_ms: Duration in milliseconds; -1 means not recorded.
            details: Additional details.
        """
        if not self._enabled or self._file is None:
            return
            
        timestamp = datetime.now().isoformat(timespec="microseconds")
        duration_str = str(duration_ms) if duration_ms >= 0 else "-"
        line = f"{timestamp} | {frame} | {phase} | {event} | {duration_str} | {details}\n"
        self._file.write(line)
        self._file.flush()

    def start(self, frame: int, phase: str, details: str = "") -> None:
        """Record the start of a phase: write a start event and save the start time.

        Args:
            frame: Current frame number.
            phase: Phase name, e.g. "cell.iteration".
            details: Additional details, default empty string.
        """
        if not self._enabled:
            return
        self._start_times[phase] = time.perf_counter()
        self.log(frame, phase, "start", -1, details)

    def end(self, frame: int, phase: str, details: str = "") -> None:
        """Record the end of a phase: automatically compute elapsed time relative to the matching start and write an end event.

        Args:
            frame: Current frame number.
            phase: Phase name, must match the corresponding start() call.
            details: Additional details, default empty string.
        """
        if not self._enabled:
            return
        start_time = self._start_times.pop(phase, None)
        duration_ms = -1
        if start_time is not None:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
        self.log(frame, phase, "end", duration_ms, details)

    @contextmanager
    def span(self, frame: int, phase: str, details: str = "") -> Generator[None, None, None]:
        """Context manager that automatically records start and end, computing elapsed time on exit.

        Usage::

            with tracer.span(frame, "core.run"):
                result = core.run(state)

        Args:
            frame: Current frame number.
            phase: Phase name.
            details: Additional details, default empty string.

        Yields:
            None.
        """
        self.start(frame, phase, details)
        try:
            yield
        finally:
            self.end(frame, phase)

    def close(self) -> None:
        """Close the trace log file handle. Idempotent — safe to call multiple times."""
        if self._file:
            self._file.close()
            self._file = None
