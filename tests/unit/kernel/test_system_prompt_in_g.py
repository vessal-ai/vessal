"""Spec §08 Digest: G holds preset assets including the system prompt;
L never carries _system_prompt."""
from __future__ import annotations

from vessal.ark.shell.hull.cell.kernel.kernel import Kernel


def test_system_prompt_in_g_not_l() -> None:
    boot = "_system_prompt = 'You are an agent.'\n"
    k = Kernel(boot_script=boot)
    assert k.G["_system_prompt"] == "You are an agent."
    assert "_system_prompt" not in k.L


def test_ping_reads_system_prompt_from_g(tmp_path) -> None:
    boot = "_system_prompt = 'sys-from-G'\n"
    db = str(tmp_path / "fl.sqlite")
    k = Kernel(boot_script=boot, db_path=db)
    ping = k.ping(None, {"globals": k.G, "locals": k.L})
    assert ping.system_prompt == "sys-from-G"
