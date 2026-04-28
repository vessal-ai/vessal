"""test_kernel_pr3_baseskill.py — regression for PR 3 / spec §6 Skill protocol."""
from __future__ import annotations

import pytest

from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
from vessal.ark.shell.hull.cell.protocol import Action, Pong
from tests.unit.kernel._ping_helpers import minimal_kernel


def _scan(kernel: Kernel) -> dict:
    """Run a single ping(None, ns) so signal_scan executes once."""
    kernel.ping(None, {"globals": kernel.G, "locals": kernel.L})
    return kernel.L["signals"]


def test_baseskill_importable_from_skills_package():
    from vessal.skills._base import BaseSkill  # noqa: F401
    from vessal.skills import BaseSkill as Reexport  # noqa: F401


def test_baseskill_requires_signal_dict_and_signal_update():
    from vessal.skills._base import BaseSkill

    class S(BaseSkill):
        name = "s"
        description = "x"

    s = S()
    assert isinstance(s.signal, dict)
    assert s.signal == {}
    assert callable(s.signal_update)


def test_systemskill_in_G_after_init():
    from vessal.skills.system import SystemSkill

    k = minimal_kernel()
    assert "_system" in k.G
    assert isinstance(k.G["_system"], SystemSkill)


def test_signals_dict_uses_triple_key():
    from vessal.skills._base import BaseSkill

    class FooSkill(BaseSkill):
        name = "foo"
        description = "y"

        def signal_update(self) -> None:
            self.signal = {"hello": "world"}

    k = minimal_kernel()
    k.L["foo"] = FooSkill()
    signals = _scan(k)

    assert ("FooSkill", "foo", "L") in signals
    assert signals[("FooSkill", "foo", "L")] == {"hello": "world"}
    # _system always present in G
    assert ("SystemSkill", "_system", "G") in signals


def test_signals_lebg_shadow_L_over_G():
    from vessal.skills._base import BaseSkill

    class C(BaseSkill):
        name = "chat"
        description = "x"

        def __init__(self, marker: str) -> None:
            super().__init__()
            self._marker = marker

        def signal_update(self) -> None:
            self.signal = {"marker": self._marker}

    k = minimal_kernel()
    k.G["chat"] = C("from-G")
    k.L["chat"] = C("from-L")

    signals = _scan(k)
    assert signals[("C", "chat", "L")] == {"marker": "from-L"}
    assert ("C", "chat", "G") not in signals  # shadowed


def test_signal_update_exception_isolates_to_error_id():
    from vessal.skills._base import BaseSkill

    class Boom(BaseSkill):
        name = "boom"
        description = "x"

        def signal_update(self) -> None:
            raise RuntimeError("kaboom")

    k = minimal_kernel()
    k.L["boom"] = Boom()
    signals = _scan(k)

    payload = signals[("Boom", "boom", "L")]
    assert "_error_id" in payload
    # _system signal still present — one Skill failure must not block others
    assert ("SystemSkill", "_system", "G") in signals


def test_no_signal_outputs_key_anymore():
    k = minimal_kernel()
    assert "_signal_outputs" not in k.L


def test_no_wake_ns_key_anymore():
    k = minimal_kernel()
    assert "_wake" not in k.L


def test_systemskill_wake_propagates_to_signal():
    k = minimal_kernel()
    k.G["_system"].wake("user_message")
    signals = _scan(k)
    payload = signals[("SystemSkill", "_system", "G")]
    assert payload.get("wake_reason") == "user_message"


def test_systemskill_carries_frame():
    k = minimal_kernel()
    k.L["_frame"] = 7

    signals = _scan(k)
    payload = signals[("SystemSkill", "_system", "G")]
    assert payload["frame"] == 7


def test_old_skillbase_module_removed():
    with pytest.raises(ImportError):
        import vessal.ark.shell.hull.skill  # noqa: F401


def test_no_BASE_SIGNALS_module():
    with pytest.raises(ImportError):
        from vessal.ark.shell.hull.cell.kernel.render import signals as _signals  # noqa: F401
