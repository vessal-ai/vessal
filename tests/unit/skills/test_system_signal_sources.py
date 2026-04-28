"""_system Skill sources its signal from authoritative places, not from
L keys that PR 5/6 deleted."""
from __future__ import annotations

from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
from vessal.ark.shell.hull.cell.protocol import Action, Pong


def _kernel(tmp_path):
    boot = "from vessal.skills.system import SystemSkill\n_system = SystemSkill()\n"
    return Kernel(boot_script=boot, db_path=str(tmp_path / "fl.sqlite"))


def test_system_signal_has_frame_and_no_legacy_keys(tmp_path) -> None:
    k = _kernel(tmp_path)
    k.ping(None, {"globals": k.G, "locals": k.L})
    sig = k.G["_system"].signal
    assert "frame" in sig
    assert "context" not in sig          # token budget is Core's job, not _system's
    assert "frame_type" not in sig       # frame_type is gone


def test_system_recent_errors_from_sqlite(tmp_path) -> None:
    k = _kernel(tmp_path)
    k.ping(None, {"globals": k.G, "locals": k.L})
    pong = Pong(think="", action=Action(operation="1/0", expect="True"))
    k.ping(pong, {"globals": k.G, "locals": k.L})
    pong2 = Pong(think="", action=Action(operation="x = 1", expect="True"))
    k.ping(pong2, {"globals": k.G, "locals": k.L})
    sig = k.G["_system"].signal
    assert "recent_errors" in sig
    assert any("ZeroDivisionError" in entry for entry in sig["recent_errors"])


def test_system_sleep_sets_sleeping_signal(tmp_path) -> None:
    """Agent calls sleep() to pause; signal shows it's sleeping."""
    k = _kernel(tmp_path)
    k.G["_system"].sleep()
    k.ping(None, {"globals": k.G, "locals": k.L})
    assert k.G["_system"].signal.get("sleeping") is True


def test_system_wake_records_reason_and_clears_sleeping(tmp_path) -> None:
    """Hull calls wake(reason) when an event resumes the agent."""
    k = _kernel(tmp_path)
    k.G["_system"].sleep()
    k.G["_system"].wake("user_message")
    k.ping(None, {"globals": k.G, "locals": k.L})
    sig = k.G["_system"].signal
    assert sig.get("sleeping", False) is False
    assert sig.get("wake_reason") == "user_message"
