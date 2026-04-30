"""describe — Namespace variable value rendering system.

Public interface: render_value(obj, detail_level) -> str

detail_level:
    "directory"  type + key metrics, one-line summary
    "diff"       value display with truncation
    "pin"        detailed observation

Imported directly from describe/, not via a renderers/ subdirectory.
"""
from vessal.ark.shell.hull.cell.kernel.describe.primitives import (
    render_int, render_float, render_bool, render_none, render_str,
)
from vessal.ark.shell.hull.cell.kernel.describe.collections import (
    render_list, render_dict, render_tuple, render_set,
)
from vessal.ark.shell.hull.cell.kernel.describe.callables import render_function, render_class
from vessal.ark.shell.hull.cell.kernel.describe.instances import render_io, render_instance
from vessal.ark.shell.hull.cell.kernel.describe.binary import render_bytes, render_module

import io
import types

__all__ = ["render_value"]

# fallback truncation limits
_FALLBACK_LIMITS = {"directory": 100, "diff": 200, "pin": 500}


def render_value(obj: object, detail_level: str) -> str:
    """Render a Python object as text at the specified detail level.

    First calls the object's __vessal_repr__(detail_level) custom renderer if present;
    then dispatches to the type-specific renderer; finally falls back to repr() with truncation.

    Args:
        obj:          Any Python object.
        detail_level: Detail level, one of "directory" / "diff" / "pin".

    Returns:
        Rendered text string, length constrained by detail_level.
    """
    custom = getattr(obj, "__vessal_repr__", None)
    if custom is not None:
        try:
            return custom(detail_level)
        except Exception:
            pass
    try:
        return _dispatch(obj, detail_level)
    except Exception:
        pass
    limit = _FALLBACK_LIMITS.get(detail_level, 200)
    r = repr(obj)
    return r if len(r) <= limit else r[:limit] + "..."


def _dispatch(obj, detail_level: str) -> str:
    if isinstance(obj, bool):
        return render_bool(obj, detail_level)
    if obj is None:
        return render_none(obj, detail_level)
    if isinstance(obj, int):
        return render_int(obj, detail_level)
    if isinstance(obj, float):
        return render_float(obj, detail_level)
    if isinstance(obj, str):
        return render_str(obj, detail_level)
    if isinstance(obj, bytes):
        return render_bytes(obj, detail_level)
    if isinstance(obj, types.ModuleType):
        return render_module(obj, detail_level)
    if isinstance(obj, dict):
        return render_dict(obj, detail_level)
    if isinstance(obj, list):
        return render_list(obj, detail_level)
    if isinstance(obj, tuple):
        return render_tuple(obj, detail_level)
    if isinstance(obj, (set, frozenset)):
        return render_set(obj, detail_level)
    if isinstance(obj, types.FunctionType):
        return render_function(obj, detail_level)
    if isinstance(obj, type):
        return render_class(obj, detail_level)
    if isinstance(obj, io.IOBase):
        return render_io(obj, detail_level)
    return render_instance(obj, detail_level)
