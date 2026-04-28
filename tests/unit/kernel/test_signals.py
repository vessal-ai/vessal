"""test_signals — Kernel signal system: base signals + SkillBase isinstance scan."""
import pytest

from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
from vessal.ark.shell.hull.skill import SkillBase


class FakeSkill(SkillBase):
    name = "fake"
    description = "Fake."
    def __init__(self):
        super().__init__()
        self.data = ""
    def _signal(self):
        if self.data:
            return ("fake", f"fake={self.data}")
        return None


def test_update_signals_collects_base_signals():
    """Base signals (goal, verdict, etc.) still collected."""
    k = Kernel()
    k.update_signals()
    outputs = k.L["_signal_outputs"]
    # system_vars always returns non-empty — check any tuple body contains "frame"
    assert any("frame" in body.lower() for _, body in outputs)


def test_update_signals_scans_skill_instances():
    """SkillBase instances in namespace have _signal() called."""
    k = Kernel()
    s = FakeSkill()
    s.data = "hello"
    k.L["my_skill"] = s
    k.update_signals()
    outputs = k.L["_signal_outputs"]
    assert any("fake=hello" in body for _, body in outputs)


def test_update_signals_skips_empty_skill_output():
    """Skill with empty _signal_output is skipped."""
    k = Kernel()
    s = FakeSkill()
    s.data = ""  # _signal() will return None
    k.L["my_skill"] = s
    k.update_signals()
    outputs = k.L["_signal_outputs"]
    assert not any("fake=" in body for _, body in outputs)


def test_update_signals_skill_error_does_not_crash():
    """Signal error in a skill is caught, not raised."""
    class BadSkill(SkillBase):
        name = "bad"
        description = "Bad."
        def _signal(self):
            raise ValueError("boom")

    k = Kernel()
    k.L["bad"] = BadSkill()
    k.update_signals()  # should NOT raise
    assert isinstance(k.L["_signal_outputs"], list)


def test_update_signals_multiple_skills():
    """Multiple skill instances all contribute."""
    k = Kernel()
    s1 = FakeSkill()
    s1.data = "one"
    s2 = FakeSkill()
    s2.data = "two"
    k.L["s1"] = s1
    k.L["s2"] = s2
    k.update_signals()
    outputs = k.L["_signal_outputs"]
    bodies = [body for _, body in outputs]
    assert any("fake=one" in b for b in bodies)
    assert any("fake=two" in b for b in bodies)


def test_skill_removed_from_ns_stops_signal():
    """Deleting skill from namespace stops its signal."""
    k = Kernel()
    s = FakeSkill()
    s.data = "present"
    k.L["s"] = s
    k.update_signals()
    outputs = k.L["_signal_outputs"]
    assert any("fake=present" in body for _, body in outputs)
    del k.L["s"]
    k.update_signals()
    outputs = k.L["_signal_outputs"]
    assert not any("fake=present" in body for _, body in outputs)


def test_init_namespace_no_signal_fns_key():
    """New namespace should NOT have _signal_fns (old mechanism removed)."""
    k = Kernel()
    assert "_signal_fns" not in k.L
