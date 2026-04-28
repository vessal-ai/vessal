"""Spec §5.5.2 档 1: DeadHandle stands in when cloudpickle fails per key."""
from __future__ import annotations

import pytest

from vessal.ark.shell.hull.cell.kernel.dead_handle import DeadHandle
from vessal.ark.shell.hull.cell.kernel.kernel import Kernel


def test_dead_handle_repr_does_not_raise() -> None:
    h = DeadHandle("file", "log_handle", "TypeError: cannot pickle '_io.TextIOWrapper'")
    s = repr(h)
    assert "DeadHandle" in s
    assert "log_handle" in s


def test_dead_handle_attribute_access_raises() -> None:
    h = DeadHandle("file", "log_handle", "not picklable")
    with pytest.raises(RuntimeError, match="dead handle"):
        h.read()


def test_dead_handle_call_raises() -> None:
    h = DeadHandle("lock", "mutex", "not picklable")
    with pytest.raises(RuntimeError, match="dead handle"):
        h()


def test_snapshot_replaces_unpicklable_with_dead_handle(tmp_path) -> None:
    k = Kernel(boot_script="")
    import threading
    k.L["lock"] = threading.Lock()      # cloudpickle cannot serialise this
    k.L["payload"] = {"x": 1}            # picklable

    snap = tmp_path / "s.pkl"
    k.snapshot(str(snap))

    k2 = Kernel(boot_script="", restore_path=str(snap))
    assert isinstance(k2.L["lock"], DeadHandle)
    assert k2.L["payload"] == {"x": 1}


def test_snapshot_does_not_fail_on_unpicklable(tmp_path) -> None:
    k = Kernel(boot_script="")
    import threading
    k.L["lock"] = threading.Lock()
    k.snapshot(str(tmp_path / "s.pkl"))   # must not raise
