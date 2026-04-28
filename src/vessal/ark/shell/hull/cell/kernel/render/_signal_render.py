"""_signal_render.py — Signal assembly (pure function).

render_signals(ns) -> str
    Reads ns["signals"] (populated by Kernel._signal_scan()),
    formats each Skill's payload as a ══════ {var_name} ══════ section,
    and joins sections with "\\n\\n".
"""
from __future__ import annotations


def render_signals(ns: dict) -> str:
    """Assemble signal section text from the spec §6 signals dict.

    Args:
        ns: Kernel namespace; reads signals (dict[tuple[cls, var, scope], dict]).

    Returns:
        All signal blocks wrapped with separator headers and concatenated. Returns "" when empty.
    """
    signals: dict = ns.get("signals", {})
    parts = []
    for (cls_name, var_name, scope), payload in signals.items():
        if not isinstance(payload, dict) or "_error_id" in payload:
            continue
        lines = [f"{k}: {v}" for k, v in payload.items() if v is not None and str(v).strip()]
        if lines:
            parts.append(f"══════ {var_name} ══════\n" + "\n".join(lines))
    return "\n\n".join(parts)
