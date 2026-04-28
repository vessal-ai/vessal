"""_signal_render.py — Signal assembly (pure function).

render_signals(ns) -> str
    Reads ns["_signal_outputs"] (populated by Kernel._signal_scan()),
    wraps each section with a ══════ {title} ══════ separator header,
    and joins sections with "\\n\\n".
"""
from __future__ import annotations


def render_signals(ns: dict) -> str:
    """Assemble signal section text, wrapping each section with a separator header.

    Args:
        ns: Kernel namespace; reads _signal_outputs (list[tuple[str, str]]).

    Returns:
        All signal blocks wrapped with separator headers and concatenated. Returns "" when empty.
    """
    outputs: list[tuple[str, str]] = ns.get("_signal_outputs", [])
    parts = []
    for title, body in outputs:
        if body and body.strip():
            parts.append(f"══════ {title} ══════\n{body}")
    return "\n\n".join(parts)
