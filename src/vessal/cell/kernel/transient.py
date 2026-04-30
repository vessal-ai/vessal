"""@transient decorator + name-based opt-in (spec §5.5.2 part 2).

Snapshot skips keys whose value's class has __vessal_transient__ = True
(@transient decorator) or whose key was registered via kernel.mark_transient(name).
Restored L simply lacks that key — same as 'first time the agent ran'."""
from __future__ import annotations

from typing import TypeVar

T = TypeVar("T", bound=type)


def transient(cls: T) -> T:
    cls.__vessal_transient__ = True
    return cls


def is_transient_value(value: object) -> bool:
    return bool(getattr(type(value), "__vessal_transient__", False))
