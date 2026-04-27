"""frame_log — SQLite-backed 5-table frame log (entries / frame_content / summary_content / signals / errors).

See docs/architecture/kernel/04-frame-log.md for the full design.
"""
from .schema import DDL, open_db
from .types import ErrorOnSource, FrameWriteSpec, SignalRow
from .writer import FrameLog

__all__ = [
    "DDL",
    "ErrorOnSource",
    "FrameLog",
    "FrameWriteSpec",
    "SignalRow",
    "open_db",
]
