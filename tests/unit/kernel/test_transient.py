"""Spec §5.5.2 part 2: @transient + kernel.mark_transient skip keys at snapshot."""
from __future__ import annotations

from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
from vessal.ark.shell.hull.cell.kernel.transient import transient


def test_transient_class_instance_not_in_restored_l(tmp_path) -> None:
    @transient
    class DbConn:
        def __init__(self) -> None:
            self.url = "sqlite://"

    k = Kernel(boot_script="")
    k.L["conn"] = DbConn()
    k.L["payload"] = {"x": 1}
    k.snapshot(str(tmp_path / "s.pkl"))

    k2 = Kernel(boot_script="", restore_path=str(tmp_path / "s.pkl"))
    assert "conn" not in k2.L
    assert k2.L["payload"] == {"x": 1}


def test_mark_transient_skips_named_key(tmp_path) -> None:
    k = Kernel(boot_script="")
    k.L["temp"] = "to-skip"
    k.L["keep"] = "kept"
    k.mark_transient("temp")
    k.snapshot(str(tmp_path / "s.pkl"))

    k2 = Kernel(boot_script="", restore_path=str(tmp_path / "s.pkl"))
    assert "temp" not in k2.L
    assert k2.L["keep"] == "kept"


def test_transient_attribute_set_on_class() -> None:
    @transient
    class X:
        pass
    assert getattr(X, "__vessal_transient__", False) is True
