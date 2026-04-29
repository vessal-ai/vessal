"""Spec §3 / §08: verdict is L["verdict"], not nested in Observation."""
from __future__ import annotations

from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
from vessal.ark.shell.hull.cell.protocol import Action, Pong


def test_verdict_lives_at_l_top_level(tmp_path) -> None:
    db = str(tmp_path / "fl.sqlite")
    k = Kernel(boot_script="", db_path=db)
    k.ping(None, {"globals": k.G, "locals": k.L})

    pong = Pong(think="", action=Action(operation="x = 1", expect="x == 1"))
    k.ping(pong, {"globals": k.G, "locals": k.L})

    assert "verdict" in k.L
    # Observation does not carry verdict any more
    assert not hasattr(k.L["observation"], "verdict")


def test_verdict_none_when_expect_empty(tmp_path) -> None:
    db = str(tmp_path / "fl.sqlite")
    k = Kernel(boot_script="", db_path=db)
    k.ping(None, {"globals": k.G, "locals": k.L})

    pong = Pong(think="", action=Action(operation="x = 1", expect=""))
    k.ping(pong, {"globals": k.G, "locals": k.L})

    assert k.L["verdict"] is None
