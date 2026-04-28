"""system_vars.py — System variable rendering (kernel/signals version).

Format example:
    frame: 1234
    context: 65% (83200/128000 tokens)
    type: work
    wake: task_ready
"""

from __future__ import annotations

from typing import Any


def render(ns: dict[str, Any]) -> str:
    """Render the system variables section.

    Args:
        ns: Kernel namespace.

    Returns:
        Rendered text (always non-empty).
    """
    lines = []

    frame = ns.get("_frame", 0)
    lines.append(f"frame: {frame}")

    context_pct = ns.get("_context_pct", 0)
    budget_total = ns.get("_budget_total", 0) or (
        ns.get("_context_budget", 128000) - ns.get("_token_budget", 4096)
    )
    used_tokens = round(budget_total * context_pct / 100) if context_pct else 0
    lines.append(f"context: {context_pct}% ({used_tokens}/{budget_total} tokens)")

    frame_type = ns.get("_frame_type", "")
    if frame_type:
        lines.append(f"type: {frame_type}")

    wake = ns.get("_wake", "")
    if wake:
        lines.append(f"wake: {wake}")

    return "\n".join(lines)
