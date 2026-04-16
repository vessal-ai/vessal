"""errors.py — Error signal: displays a summary of the most recent ErrorRecords."""
from __future__ import annotations

from typing import Any


def render(ns: dict[str, Any]) -> str:
    """Render the most recent 3 error summaries.

    Args:
        ns: Kernel namespace; reads _errors (list[ErrorRecord]).

    Returns:
        Error summary text. Returns "" when there are no errors.
    """
    errors = ns.get("_errors", [])
    if not errors:
        return ""
    recent = errors[-3:]
    lines = [getattr(e, "summary", lambda: repr(e))() for e in recent]
    if len(errors) > 3:
        lines.insert(0, f"({len(errors)} errors, showing most recent 3)")
    return "\n".join(lines)
