"""_signal_render.py — Signal assembly (pure function).

Reads L["signals"] (spec §6 dict[(class_name, var_name, scope), payload]),
wraps each entry with a section header, and joins with double newlines.
"""
from __future__ import annotations


def render_signals(ns: dict) -> str:
    signals = ns.get("signals") or {}
    parts: list[str] = []
    for (class_name, var_name, _scope), payload in signals.items():
        if not isinstance(payload, dict) or not payload:
            continue
        if "_error_id" in payload:
            body = f"(error: id={payload['_error_id']})"
        else:
            body_lines = []
            for k, v in payload.items():
                v_text = v if isinstance(v, str) else str(v)
                if "\n" in v_text:
                    body_lines.append(f"{k}:")
                    for line in v_text.splitlines():
                        body_lines.append(f"  {line}")
                else:
                    body_lines.append(f"{k}: {v_text}")
            body = "\n".join(body_lines)
        parts.append(f"══════ {var_name} ({class_name}) ══════\n{body}")
    return "\n\n".join(parts)
