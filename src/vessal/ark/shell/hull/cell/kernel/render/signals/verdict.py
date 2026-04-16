"""verdict.py — Verification result signal (kernel/signals version).

Displays the expect verification result (_verdict) from the most recent frame.
Returns "" when _verdict is None, taking no space.
"""

from __future__ import annotations

from typing import Any


def render(ns: dict[str, Any]) -> str:
    """Render the verification result section.

    Args:
        ns: Kernel namespace. Reads ns["_verdict"] (Verdict or None).

    Returns:
        Rendered text; returns "" when _verdict is None.
    """
    verdict = ns.get("_verdict")
    if verdict is None:
        return ""

    summary = f"{verdict.passed}/{verdict.total} assertions passed"
    if not verdict.failures:
        return summary

    lines = [summary]
    for failure in verdict.failures:
        lines.append(f"  [{failure.kind}] {failure.assertion} — {failure.message}")
    return "\n".join(lines)
