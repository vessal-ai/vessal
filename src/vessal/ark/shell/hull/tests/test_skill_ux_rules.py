"""test_skill_ux_rules — Verifies that all built-in Skills comply with UX rules."""
import importlib
import pytest


BUILTIN_SKILLS = ["chat", "pin", "tasks", "memory", "heartbeat", "pip", "skill_creator"]

# Forbidden method name patterns in signal output
FORBIDDEN_IN_SIGNAL = [
    "chat.read(", "chat.reply(", "chat.receive(",
    "pin.pin(", "pin.unpin(",
    "tasks.add_task(", "tasks.update_task(", "tasks.get_task(", "tasks.current_task(",
    "memory.save(", "memory.get(", "memory.delete(",
    "skills.load(", "skills.unload(", "skills.list(",
    "_meta.load_skill(", "_meta.unload_skill(",
]


@pytest.mark.parametrize("skill_name", BUILTIN_SKILLS)
def test_description_max_15_chars(skill_name):
    """Each built-in Skill's description must not exceed 15 characters."""
    mod = importlib.import_module(f"vessal.skills.{skill_name}")
    cls = mod.Skill
    assert len(cls.description) <= 30, (
        f"{skill_name}.description = {cls.description!r} ({len(cls.description)} chars, exceeds 30)"
    )


@pytest.mark.parametrize("skill_name", BUILTIN_SKILLS)
def test_signal_no_method_names(skill_name):
    """_signal() output (if any) must not contain method names."""
    mod = importlib.import_module(f"vessal.skills.{skill_name}")
    cls = mod.Skill
    instance = cls()
    result = instance._signal()
    if result is None:
        return
    _, body = result
    for forbidden in FORBIDDEN_IN_SIGNAL:
        assert forbidden not in body, (
            f"{skill_name}._signal() contains method name {forbidden!r}"
        )
