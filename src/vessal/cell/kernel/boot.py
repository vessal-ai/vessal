"""boot.py — compose_boot_script: pure string assembly for spec §7.4.

Hull supplies an ordered list of BootSkillEntry; this module returns the
Python source string Kernel will exec on (G, G). Pure function — no IO,
no exec, no filesystem, no environ reads.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BootSkillEntry:
    """One Skill instantiation for the boot script.

    Attributes:
        var_name: name the instance will bind to in G (e.g. "_system", "chat").
        class_name: class symbol exported by `skills/__init__.py`
            (e.g. "System", "Chat", "SkillManager").
        kwargs_repr: literal Python source for constructor kwargs;
            "" for no-arg construction; "main_db_path='/tmp/x'" for kwargs.
    """
    var_name: str
    class_name: str
    kwargs_repr: str = ""


_HEADER = "import importlib, copy, json"


def compose_boot_script(entries: list[BootSkillEntry]) -> str:
    """Return the Python source for one boot run.

    Layout: `import importlib, copy, json`, then a single
    `from skills import <Cls1>, <Cls2>, …`, then per-Skill
    `<var_name> = <class_name>(<kwargs_repr>)`.

    Args:
        entries: ordered list of Skills to instantiate.

    Returns:
        Python source string ending with a trailing newline.
    """
    lines: list[str] = [_HEADER]
    if entries:
        seen: dict[str, None] = {}
        for entry in entries:
            seen.setdefault(entry.class_name, None)
        lines.append(f"from skills import {', '.join(seen.keys())}")
        lines.append("")
        for entry in entries:
            lines.append(f"{entry.var_name} = {entry.class_name}({entry.kwargs_repr})")
    return "\n".join(lines) + "\n"
