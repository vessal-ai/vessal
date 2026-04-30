"""binary.py — bytes and module type rendering.

bytes:
    directory   size (B / KB / MB)
    diff        "bytes, N bytes"
    pin         "bytes, N bytes, hex: <first 20 bytes hex>..."

module:
    all views   "module name" or "module name vX.Y.Z"
"""
from __future__ import annotations

import types


def render_bytes(obj: bytes, detail_level: str) -> str:
    """Render a bytes object."""
    size = len(obj)

    if detail_level == "directory":
        if size >= 1024 * 1024:
            return f"bytes, {size // (1024 * 1024)}MB"
        elif size >= 1024:
            return f"bytes, {size // 1024}KB"
        else:
            return f"bytes, {size}B"

    if detail_level == "pin":
        hex_preview = obj[:20].hex()
        return f"bytes, {size} bytes, hex: {hex_preview}..."

    # diff
    return f"bytes, {size} bytes"


def render_module(obj: types.ModuleType, detail_level: str) -> str:
    """Render a module object; format is the same for all views."""
    name = getattr(obj, "__name__", repr(obj))
    version = getattr(obj, "__version__", None)
    if version:
        return f"module {name} v{version}"
    return f"module {name}"
