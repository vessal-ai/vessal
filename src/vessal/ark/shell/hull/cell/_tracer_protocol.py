"""_tracer_protocol.py — Structural type Cell needs for tracing.

Cell does NOT import Tracer. Any object whose methods match this Protocol
is accepted at the Cell boundary; Hull injects a concrete Tracer instance.
"""
from __future__ import annotations
from typing import Protocol


class TracerLike(Protocol):
    """Minimum surface Cell uses for tracing. Static type checkers enforce the contract."""

    def start(self, frame: int, phase: str, details: str = "") -> None: ...
    def end(self, frame: int, phase: str, details: str = "") -> None: ...
    def log(self, frame: int, phase: str, event: str, duration_ms: int = -1, details: str = "") -> None: ...
    # span() is intentionally excluded: Cell never calls tracer.span(); it is a Hull-level concern.
