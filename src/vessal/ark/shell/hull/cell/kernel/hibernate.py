"""hibernate/wake dispatch helpers (spec §5.5.2 part 3 + §5.5.3).

Snapshot side: an object implementing __vessal_hibernate__ gets to provide
its own picklable state; the resulting tuple lands in the snapshot instead
of the live object. If hibernate raises, the snapshot writer falls back to
DeadHandle (spec §5.5.3 error model).

Restore side: the tuple is detected and __vessal_wake__ is called on a
fresh instance via cls.__new__ (no __init__). If wake raises, the value
becomes an UnresolvedRef so the agent sees the failure but L still loads.

Marker tuple shape:
    (HIBERNATED_MARKER, cls, state_dict)
"""
from __future__ import annotations

from typing import Any

HIBERNATED_MARKER: str = "__vessal_hibernated__"


def has_hibernate(obj: object) -> bool:
    return callable(getattr(obj, "__vessal_hibernate__", None))


def call_hibernate(obj: object) -> tuple[str, type, Any]:
    """Returns the marker tuple. Raises whatever __vessal_hibernate__ raises."""
    state = obj.__vessal_hibernate__()
    return (HIBERNATED_MARKER, type(obj), state)


def is_hibernated_tuple(value: object) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 3
        and value[0] == HIBERNATED_MARKER
    )


def call_wake(value: tuple) -> object:
    """Reconstruct the object via __vessal_wake__. Raises on wake failure."""
    _, cls, state = value
    obj = cls.__new__(cls)
    obj.__vessal_wake__(state)
    return obj
