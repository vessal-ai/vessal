"""collections.py — Collection type rendering (list, dict, set, tuple).

Rules for three detail_levels (using list as example):
    directory   type + item count, no content shown
    diff        small(<10) full repr | medium(10-1000) first 3 items + "[N items]" | large(>1000) first 3 + "[N items]"
    pin         small(<10) full repr | medium(10-1000) first 5 items + "[N items]" | large(>1000) first 3 + "[N items]"
"""


def render_list(obj: list, detail_level: str) -> str:
    """Render a list."""
    n = len(obj)
    if detail_level == "directory":
        return f"list, {n} items"
    if n < 10:
        return repr(obj)
    if detail_level == "diff" or n > 1000:
        items = obj[:3]
        return repr(items) + f"...[{n} items]"
    # pin, 10 <= n <= 1000
    items = obj[:5]
    return repr(items) + f"...[{n} items]"


def render_dict(obj: dict, detail_level: str) -> str:
    """Render a dict."""
    n = len(obj)
    if detail_level == "directory":
        return f"dict, {n} items"
    if n < 10:
        return repr(obj)
    pairs = list(obj.items())
    if detail_level == "diff" or n > 1000:
        preview = dict(pairs[:3])
        return repr(preview) + f"...[{n} items]"
    # pin, 10 <= n <= 1000
    preview = dict(pairs[:5])
    return repr(preview) + f"...[{n} items]"


def render_tuple(obj: tuple, detail_level: str) -> str:
    """Render a tuple."""
    n = len(obj)
    if detail_level == "directory":
        return f"tuple, {n} items"
    if n < 10:
        return repr(obj)
    if detail_level == "diff" or n > 1000:
        items = obj[:3]
        return repr(items) + f"...[{n} items]"
    items = obj[:5]
    return repr(items) + f"...[{n} items]"


def render_set(obj: set, detail_level: str) -> str:
    """Render a set / frozenset."""
    n = len(obj)
    type_name = type(obj).__name__
    if detail_level == "directory":
        return f"{type_name}, {n} items"
    lst = list(obj)
    if n < 10:
        return repr(obj)
    if detail_level == "diff" or n > 1000:
        return repr(lst[:3]) + f"...[{n} items]"
    return repr(lst[:5]) + f"...[{n} items]"
