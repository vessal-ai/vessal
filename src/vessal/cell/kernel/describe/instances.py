"""instances.py — Instance, IO object, and connection-like object rendering.

IO objects (io.IOBase subclasses): show type name + open/closed status.
Connection-like objects: show type name + connected/closed status.
Plain instances: show type name (directory), or truncated repr (diff/pin).
"""
from __future__ import annotations

import io


def render_io(obj: io.IOBase, detail_level: str) -> str:
    """Render an IO object (StringIO, BytesIO, file handles, etc.)."""
    status = "closed" if obj.closed else "open"
    type_name = type(obj).__name__
    return f"{type_name} [{status}]"


def render_instance(obj, detail_level: str) -> str:
    """Render a plain instance. directory shows only the type name; diff/pin uses truncated repr."""
    type_name = type(obj).__name__

    if detail_level == "directory":
        return type_name

    limit = 200 if detail_level == "diff" else 500
    r = repr(obj)
    if len(r) <= limit:
        return r
    return r[:limit] + "..."
