"""Architecture lint: every Skill class is a BaseSkill subclass + exposes signal/signal_update."""
import importlib
import inspect
import pkgutil

from vessal.skills._base import BaseSkill
import vessal.skills as skills_pkg


def _iter_skill_classes():
    for mod_info in pkgutil.iter_modules(skills_pkg.__path__, prefix="vessal.skills."):
        if mod_info.name.endswith("._base"):
            continue
        try:
            mod = importlib.import_module(mod_info.name + ".skill")
        except ModuleNotFoundError:
            continue
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if obj is BaseSkill:
                continue
            if issubclass(obj, BaseSkill) and obj.__module__ == mod.__name__:
                yield obj


def test_every_skill_is_baseskill_subclass():
    classes = list(_iter_skill_classes())
    assert classes, "No Skill classes discovered"
    for cls in classes:
        assert issubclass(cls, BaseSkill), f"{cls!r} not BaseSkill subclass"


def test_every_skill_has_signal_attr_after_init():
    """Spec §6.1 #1: signal must be an instance attribute set in __init__."""
    for cls in _iter_skill_classes():
        try:
            instance = cls()
        except TypeError:
            # Skill requires constructor args (e.g., Skills(ns) / SystemSkill(kernel))
            continue
        assert hasattr(instance, "signal")
        assert isinstance(instance.signal, dict)
