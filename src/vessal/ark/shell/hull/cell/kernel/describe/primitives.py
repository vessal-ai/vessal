"""primitives.py — Primitive type rendering (int, float, bool, None, str).

Truncation rules for three detail_levels (str):
    directory   type + character count, no content shown
    diff        short(<200) full | medium(200-2000) first 100 chars + "[N chars]" | long(>2000) first 50 chars + "[N chars]"
    pin         short(<200) full | medium(200-2000) first 500 chars + "[N chars]" | long(>2000) first 200 chars + "[N chars]"
"""


def render_int(obj: int, detail_level: str) -> str:
    """Render an integer. directory: type name; others: str(obj)."""
    if detail_level == "directory":
        return "int"
    return str(obj)


def render_float(obj: float, detail_level: str) -> str:
    """Render a float. directory: type name; others: str(obj)."""
    if detail_level == "directory":
        return "float"
    return str(obj)


def render_bool(obj: bool, detail_level: str) -> str:
    """Render a bool. directory: type name; others: str(obj)."""
    if detail_level == "directory":
        return "bool"
    return str(obj)


def render_none(_obj, detail_level: str) -> str:
    """Render None. Returns "None" for all views."""
    return "None"


def render_str(obj: str, detail_level: str) -> str:
    """Render a string with truncation length controlled by detail_level.

    directory: type + character count (no content shown).
    diff:      short strings shown in full; medium/long truncated with character count appended.
    pin:       more lenient truncation thresholds (500/200 chars).
    """
    n = len(obj)
    if detail_level == "directory":
        return f"str, {n} chars"

    if detail_level == "diff":
        if n < 200:
            return obj
        elif n <= 2000:
            return obj[:100] + f"[{n} chars]"
        else:
            return obj[:50] + f"[{n} chars]"

    # pin (and lenient fallback for unknown detail_level)
    if n < 200:
        return obj
    elif n <= 2000:
        return obj[:500] + f"[{n} chars]"
    else:
        return obj[:200] + f"[{n} chars]"
