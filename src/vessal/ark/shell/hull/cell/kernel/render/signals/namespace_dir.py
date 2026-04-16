"""namespace_dir.py — Namespace directory view rendering (kernel/signals version).

Displays the list of user variables (_ prefix system variables and builtins are excluded).
Each variable is shown on one line in "name: <directory view>" format.

Sort order: descending by _ns_meta[name]["last_used"] (most recently used first),
variables without _ns_meta entries appear last.

When over budget, truncates from the end (oldest variables), appending "...[N more variables]".
"""

from __future__ import annotations

from typing import Any

from vessal.ark.shell.hull.cell.kernel.describe import render_value
from vessal.ark.util.token_util import estimate_tokens

_DEFAULT_BUDGET = 4000


def render(ns: dict[str, Any], budget: int = _DEFAULT_BUDGET) -> str:
    """Render the namespace directory.

    Args:
        ns:     Kernel namespace.
        budget: Maximum token count available to this module (optional, default 4000).

    Returns:
        Rendered text; returns "(empty)" when there are no user variables.
    """
    builtin_names = set(ns.get("_builtin_names", []))
    ns_meta = ns.get("_ns_meta", {})

    user_vars = [k for k in ns if not k.startswith("_") and k not in builtin_names]

    if not user_vars:
        return "(empty)"

    def _sort_key(name: str):
        meta = ns_meta.get(name)
        if meta:
            return (-meta.get("last_used", 0),)
        return (float("inf"),)

    user_vars.sort(key=_sort_key)

    lines = []
    for name in user_vars:
        obj = ns[name]
        lines.append(f"  {name}: {render_value(obj, 'directory')}")

    result = "\n".join(lines)
    if estimate_tokens(result) <= budget:
        return result

    kept = []
    total_vars = len(user_vars)
    for i, name in enumerate(user_vars):
        obj = ns[name]
        kept.append(f"  {name}: {render_value(obj, 'directory')}")
        candidate = "\n".join(kept)
        remaining = total_vars - (i + 1)
        if remaining > 0:
            candidate += f"\n  ...[{remaining} more variables]"
        if estimate_tokens(candidate) > budget:
            kept.pop()
            remaining = total_vars - i
            suffix = f"\n  ...[{remaining} more variables]" if remaining > 0 else ""
            return "\n".join(kept) + suffix

    return "\n".join(kept)
