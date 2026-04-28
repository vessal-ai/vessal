"""Spec §5.5.2 part 3 + §5.5.3: hibernate/wake protocol."""
from __future__ import annotations

import pytest

from vessal.ark.shell.hull.cell.kernel.dead_handle import DeadHandle
from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
from vessal.ark.shell.hull.cell.kernel.lenient import UnresolvedRef


class GoodHttpSkill:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.connection_count = 5
        self.opened = True

    def __vessal_hibernate__(self) -> dict:
        self.opened = False
        return {"base_url": self.base_url}

    def __vessal_wake__(self, state: dict) -> None:
        self.base_url = state["base_url"]
        self.connection_count = 0
        self.opened = True


class HibernateRaises:
    def __vessal_hibernate__(self) -> dict:
        raise RuntimeError("cannot hibernate")


class WakeRaises:
    def __init__(self) -> None:
        self.x = 1

    def __vessal_hibernate__(self) -> dict:
        return {"x": self.x}

    def __vessal_wake__(self, state: dict) -> None:
        raise RuntimeError("cannot wake")


def test_hibernate_round_trip(tmp_path) -> None:
    k = Kernel(boot_script="")
    k.L["http"] = GoodHttpSkill("https://api.example.com")
    k.snapshot(str(tmp_path / "s.pkl"))
    assert k.L["http"].opened is False     # hibernate ran

    k2 = Kernel(boot_script="", restore_path=str(tmp_path / "s.pkl"))
    obj = k2.L["http"]
    assert isinstance(obj, GoodHttpSkill)
    assert obj.base_url == "https://api.example.com"
    assert obj.opened is True              # wake reopened
    assert obj.connection_count == 0       # wake reset transient counter


def test_hibernate_raise_degrades_to_dead_handle(tmp_path) -> None:
    k = Kernel(boot_script="")
    k.L["bad"] = HibernateRaises()
    k.snapshot(str(tmp_path / "s.pkl"))    # must not raise

    k2 = Kernel(boot_script="", restore_path=str(tmp_path / "s.pkl"))
    assert isinstance(k2.L["bad"], DeadHandle)
    assert "cannot hibernate" in repr(k2.L["bad"])


def test_wake_raise_degrades_to_unresolved_ref(tmp_path) -> None:
    k = Kernel(boot_script="")
    k.L["bad_wake"] = WakeRaises()
    k.snapshot(str(tmp_path / "s.pkl"))

    k2 = Kernel(boot_script="", restore_path=str(tmp_path / "s.pkl"))
    assert isinstance(k2.L["bad_wake"], UnresolvedRef)
    assert "cannot wake" in repr(k2.L["bad_wake"])
