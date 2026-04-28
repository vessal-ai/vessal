"""Test that Kernel only scans BaseSkill instances (spec §6), not arbitrary duck-typed objects."""
from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
from vessal.skills._base import BaseSkill
from tests.unit.kernel._ping_helpers import _ns


class FakeSignalSource:
    """Not a BaseSkill subclass; has old _signal() duck-type method — should NOT be picked up."""
    def _signal(self):
        return ("fake", "test signal active")


def test_kernel_ignores_duck_typed_signal_non_baseskill():
    """Non-BaseSkill objects with _signal() are ignored by _signal_scan."""
    k = Kernel()
    k.L["fake"] = FakeSignalSource()
    k.ping(None, _ns(k))
    signals = k.L["signals"]
    # No entry for FakeSignalSource — only BaseSkill subclasses are scanned
    assert not any(cls == "FakeSignalSource" for cls, _, _ in signals)


def test_kernel_skips_objects_without_signal():
    """Plain objects in namespace do not appear in signals."""
    k = Kernel()
    k.L["plain"] = "just a string"
    k.L["number"] = 42
    k.ping(None, _ns(k))
    signals = k.L["signals"]
    assert isinstance(signals, dict)
    # Only SystemSkill from G should be present
    assert all(isinstance(key, tuple) and len(key) == 3 for key in signals)
