"""test_signals — Kernel signal system: BaseSkill.signal_update() scan."""
import pytest

from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
from vessal.skills._base import BaseSkill
from tests.unit.kernel._ping_helpers import _ns


class FakeSkill(BaseSkill):
    name = "fake"
    description = "Fake."
    def __init__(self):
        super().__init__()
        self.data = ""

    def signal_update(self) -> None:
        if self.data:
            self.signal = {"value": f"fake={self.data}"}
        else:
            self.signal = {}


def test_update_signals_collects_system_skill():
    """SystemSkill in G is always scanned and provides frame/context signal."""
    k = Kernel()
    k.ping(None, _ns(k))
    signals = k.L["signals"]
    system_payload = signals.get(("SystemSkill", "_system", "G"), {})
    # system_vars always returns non-empty — check "frame" in payload
    assert "frame" in system_payload


def test_update_signals_scans_skill_instances():
    """BaseSkill instances in namespace have signal_update() called."""
    k = Kernel()
    s = FakeSkill()
    s.data = "hello"
    k.L["my_skill"] = s
    k.ping(None, _ns(k))
    signals = k.L["signals"]
    assert ("FakeSkill", "my_skill", "L") in signals
    assert signals[("FakeSkill", "my_skill", "L")] == {"value": "fake=hello"}


def test_update_signals_skips_empty_skill_output():
    """Skill with empty signal dict is still recorded (empty payload)."""
    k = Kernel()
    s = FakeSkill()
    s.data = ""  # signal_update() sets signal = {}
    k.L["my_skill"] = s
    k.ping(None, _ns(k))
    signals = k.L["signals"]
    assert ("FakeSkill", "my_skill", "L") in signals
    assert signals[("FakeSkill", "my_skill", "L")] == {}


def test_update_signals_skill_error_does_not_crash():
    """Signal error in a skill is caught, not raised."""
    class BadSkill(BaseSkill):
        name = "bad"
        description = "Bad."
        def signal_update(self) -> None:
            raise ValueError("boom")

    k = Kernel()
    k.L["bad"] = BadSkill()
    k.ping(None, _ns(k))  # should NOT raise
    signals = k.L["signals"]
    assert ("BadSkill", "bad", "L") in signals
    assert "_error_id" in signals[("BadSkill", "bad", "L")]


def test_update_signals_multiple_skills():
    """Multiple skill instances all contribute."""
    k = Kernel()
    s1 = FakeSkill()
    s1.data = "one"
    s2 = FakeSkill()
    s2.data = "two"
    k.L["s1"] = s1
    k.L["s2"] = s2
    k.ping(None, _ns(k))
    signals = k.L["signals"]
    assert signals[("FakeSkill", "s1", "L")] == {"value": "fake=one"}
    assert signals[("FakeSkill", "s2", "L")] == {"value": "fake=two"}


def test_skill_removed_from_ns_stops_signal():
    """Deleting skill from namespace stops its signal."""
    k = Kernel()
    s = FakeSkill()
    s.data = "present"
    k.L["s"] = s
    k.ping(None, _ns(k))
    assert ("FakeSkill", "s", "L") in k.L["signals"]
    del k.L["s"]
    k.ping(None, _ns(k))
    assert ("FakeSkill", "s", "L") not in k.L["signals"]


def test_init_namespace_no_signal_fns_key():
    """New namespace should NOT have _signal_fns (old mechanism removed)."""
    k = Kernel()
    assert "_signal_fns" not in k.L
