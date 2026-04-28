"""Test that Kernel discovers signals via duck-typing, not isinstance."""
from vessal.ark.shell.hull.cell.kernel.kernel import Kernel


class FakeSignalSource:
    """Not a SkillBase subclass, but has _signal protocol."""
    def _signal(self):
        return ("fake", "test signal active")


def test_kernel_discovers_signal_via_ducktype():
    k = Kernel()
    k.L["fake"] = FakeSignalSource()
    k.update_signals()
    outputs = k.L["_signal_outputs"]
    assert any("test signal active" in body for _, body in outputs)


def test_kernel_skips_objects_without_signal():
    k = Kernel()
    k.L["plain"] = "just a string"
    k.L["number"] = 42
    k.update_signals()
    # Should not crash, signal_outputs should only have base signals
    assert isinstance(k.L["_signal_outputs"], list)
