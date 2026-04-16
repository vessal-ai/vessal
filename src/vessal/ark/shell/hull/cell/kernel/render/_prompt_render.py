"""_prompt_render.py — Skill cognitive protocol collection and rendering.

Duck-type scans namespace for _prompt() methods, collects (condition, methodology) tuples,
and renders them as structured skill protocol text. Parallel to _signal_render.py.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def collect_skill_protocols(ns: dict) -> list[tuple[str, str, str]]:
    """Duck-type scan namespace to collect _prompt() return values.

    Iterates over all objects in the namespace that have a _prompt method,
    calls _prompt(), and collects non-empty (condition, methodology) return values.
    Errors are silently logged and do not interrupt processing.

    Args:
        ns: Kernel namespace dict.

    Returns:
        list of (skill_name, condition, methodology) 3-tuples.
    """
    protocols: list[tuple[str, str, str]] = []
    for obj in list(ns.values()):
        if hasattr(obj, "_prompt") and callable(getattr(obj, "_prompt")):
            try:
                result = obj._prompt()
                if isinstance(result, tuple) and len(result) == 2:
                    condition, methodology = result
                    if (isinstance(methodology, str) and methodology.strip()
                            and isinstance(condition, str) and condition.strip()):
                        name = getattr(obj, "name", "?")
                        protocols.append((str(name), str(condition), methodology))
            except Exception as e:
                obj_name = getattr(obj, "name", repr(obj))
                logger.warning("Skill protocol '%s' collection failed: %s", obj_name, e)
    return protocols


def render_skill_protocols(ns: dict) -> str:
    """Assemble skill protocol section text.

    Each protocol is rendered as:
        ── {name} ──
        When {condition}:
        {methodology}

    Args:
        ns: Kernel namespace dict.

    Returns:
        Rendered skill protocol text. Returns empty string when there is no content.
    """
    protocols = collect_skill_protocols(ns)
    if not protocols:
        return ""
    parts: list[str] = []
    for name, condition, methodology in protocols:
        parts.append(f"── {name} ──\nWhen {condition}:\n{methodology}")
    return "\n\n".join(parts)
