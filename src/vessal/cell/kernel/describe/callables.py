"""callables.py — Function and class rendering.

function:
    directory   "function(sig)"
    diff        "function name(sig), N lines"
    pin         full source (<= 30 lines) or signature + first 10 lines

class:
    directory   "class Name, N methods"
    diff        "class Name, N methods, N lines"
    pin         full source (<= 50 lines) or method signature list
"""
from __future__ import annotations

import inspect
import types


def _get_source(obj) -> str | None:
    """Return the source text for a function or class via stdlib inspect.

    Returns None for built-ins, C extensions, or any object whose
    co_filename is not registered in linecache. Kernel-defined
    functions and classes resolve via the linecache + sys.modules
    entries created by source_cache.register().
    """
    try:
        return inspect.getsource(obj)
    except (OSError, TypeError):
        return None


def _safe_sig(obj) -> str:
    """Safely get a signature string; returns '(...)' on failure."""
    try:
        return str(inspect.signature(obj))
    except (ValueError, TypeError):
        return "(...)"


def render_function(obj: types.FunctionType, detail_level: str) -> str:
    """Render a function object."""
    sig = _safe_sig(obj)

    if detail_level == "directory":
        return f"function{sig}"

    source = _get_source(obj)
    n_lines = len(source.splitlines()) if source else "?"

    if detail_level == "diff":
        return f"function {obj.__name__}{sig}, {n_lines} lines"

    # pin
    if source:
        lines = source.splitlines()
        if len(lines) <= 30:
            return source
        first_10 = "\n".join(lines[:10])
        return f"def {obj.__name__}{sig}:\n{first_10}"
    return f"function {obj.__name__}{sig}"


def render_class(obj: type, detail_level: str) -> str:
    """Render a class object."""
    methods = [m for m in dir(obj) if not m.startswith("__")]
    n_methods = len(methods)

    if detail_level == "directory":
        return f"class {obj.__name__}, {n_methods} methods"

    source = _get_source(obj)
    n_lines = len(source.splitlines()) if source else "?"

    if detail_level == "diff":
        return f"class {obj.__name__}, {n_methods} methods, {n_lines} lines"

    # pin
    if source:
        lines = source.splitlines()
        if len(lines) <= 50:
            return source
        # show method signature list when source is too long
        sigs = []
        for attr_name in dir(obj):
            if attr_name.startswith("__"):
                continue
            attr = getattr(obj, attr_name, None)
            if callable(attr):
                sigs.append(f"  def {attr_name}{_safe_sig(attr)}")
        return f"class {obj.__name__}:\n" + "\n".join(sigs)
    return f"class {obj.__name__}, {n_methods} methods"
