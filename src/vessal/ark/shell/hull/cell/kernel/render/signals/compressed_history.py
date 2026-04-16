"""compressed_history.py — Compressed history signal (built-in).

Downgraded from compression skill to a built-in signal. Displays the content of
the _compressed_history variable.
"""
from __future__ import annotations


def render(ns: dict) -> str:
    """Render the compressed history section.

    Args:
        ns: Kernel namespace dict; reads the "_compressed_history" key.

    Returns:
        Compressed history text; returns empty string when there is no history.
    """
    history = ns.get("_compressed_history", "")
    if not history or not history.strip():
        return ""
    return history
