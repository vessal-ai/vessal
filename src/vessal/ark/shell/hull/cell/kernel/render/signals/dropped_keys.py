"""dropped_keys.py — Reconstruction hint signal for variables lost after restart.

When snapshot falls back to partial serialization, non-serializable variables in the
namespace are recorded in _dropped_keys (list) and _dropped_keys_context (dict).
After restore, this signal prompts the Agent about which variables need to be
reconstructed and provides the original creation code.

Returns "" when both keys are absent or _dropped_keys is empty.
"""

from __future__ import annotations

from typing import Any


def render(ns: dict[str, Any]) -> str:
    """Render the lost variable reconstruction hint section.

    Args:
        ns: Kernel namespace. Reads _dropped_keys (list) and
            _dropped_keys_context (dict, key → original operation string).

    Returns:
        Rendered text; returns "" when there are no dropped variables.
    """
    dropped = ns.get("_dropped_keys", [])
    if not dropped:
        return ""
    context = ns.get("_dropped_keys_context", {})
    lines = []
    for key in dropped:
        op = context.get(key, "")
        if op:
            lines.append(f"  {key}: original creation code: {op[:100]}")
        else:
            lines.append(f"  {key}: no creation record")
    return "\n".join(lines)
