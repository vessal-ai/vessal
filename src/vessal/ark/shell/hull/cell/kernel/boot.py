"""boot.py — compose_boot_script: pure string assembly for spec §7.4.

Hull supplies an ordered list of BootSkillEntry; this module returns the Python
source string Kernel will exec on (G, G). Pure function — no IO, no exec, no
filesystem, no environ reads. Hull owns environ injection BEFORE Kernel exec
runs the script.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BootSkillEntry:
    """One Skill to be instantiated by the boot script.

    Attributes:
        var_name: the name the instance will bind to in G (e.g. "_system", "chat").
        import_path: dotted import path of the module (e.g. "vessal.skills.chat").
        class_name: class symbol exported by that module (e.g. "Chat").
        kwargs_repr: literal Python source for constructor kwargs;
            "" for no-arg construction; "model=\"gpt-4\"" for kwargs.
    """

    var_name: str
    import_path: str
    class_name: str
    kwargs_repr: str = ""


_HEADER = "import importlib, copy, json\n"


def compose_boot_script(entries: list[BootSkillEntry]) -> str:
    """Return the Python source for one boot run.

    Spec §7.4 layout: `import importlib, copy, json` first, then per-Skill
    `from <import_path> import <class_name>`, then per-Skill
    `<var_name> = <class_name>(<kwargs_repr>)`.

    Args:
        entries: ordered Skill list.

    Returns:
        A complete Python source string ending with a trailing newline.
    """
    if not entries:
        return _HEADER

    imports = "\n".join(
        f"from {e.import_path} import {e.class_name}" for e in entries
    )
    constructions = "\n".join(
        f"{e.var_name} = {e.class_name}({e.kwargs_repr})" for e in entries
    )
    return f"{_HEADER}{imports}\n\n{constructions}\n"
