# tests/unit/kernel/test_boot_script_no_name_collision.py
"""Regression for the 2026-04-30 boot-script class-name collision.

When multiple skills share an exported class name (e.g. all aliased to `Skill`),
exec-ing the generated boot script in one namespace silently rebinds the name
to whichever import comes last, and every var ends up pointing at the same class.
"""
from __future__ import annotations

from vessal.ark.shell.hull.cell.kernel.boot import compose_boot_script, BootSkillEntry


def test_boot_script_uses_unique_class_per_var():
    """compose_boot_script must produce a script that, when exec'd, binds each
    var_name to its own skill's class — not to a single shared name."""
    entries = [
        BootSkillEntry("_system", "System"),
        BootSkillEntry("chat", "Chat"),
        BootSkillEntry("skill_manager", "SkillManager"),
    ]
    script = compose_boot_script(entries)

    # Stub out the `skills` package so we don't depend on the project layout.
    class System: pass
    class Chat: pass
    class SkillManager: pass

    import sys, types
    fake = types.ModuleType("skills")
    fake.System = System
    fake.Chat = Chat
    fake.SkillManager = SkillManager
    sys.modules["skills"] = fake
    try:
        ns: dict = {}
        exec(compile(script, "<boot>", "exec"), ns, ns)
    finally:
        del sys.modules["skills"]

    assert ns["_system"].__class__ is System
    assert ns["chat"].__class__ is Chat
    assert ns["skill_manager"].__class__ is SkillManager


def test_boot_script_emits_single_consolidated_import():
    """One `from skills import …` line, not one per skill — keeps the LLM's
    pong window short."""
    entries = [
        BootSkillEntry("_system", "System"),
        BootSkillEntry("chat", "Chat"),
    ]
    script = compose_boot_script(entries)
    skills_imports = [ln for ln in script.splitlines() if ln.startswith("from skills import")]
    assert len(skills_imports) == 1, f"expected one consolidated import, got: {skills_imports}"
    assert "System" in skills_imports[0]
    assert "Chat" in skills_imports[0]


def test_boot_script_supports_kwargs_repr():
    entries = [BootSkillEntry("compaction", "Compaction", "main_db_path='/tmp/x'")]
    script = compose_boot_script(entries)
    assert "compaction = Compaction(main_db_path='/tmp/x')" in script
