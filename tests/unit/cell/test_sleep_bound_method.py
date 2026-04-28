def test_sleep_is_bound_method():
    from vessal.ark.shell.hull.cell.kernel import Kernel
    from vessal.ark.shell.hull.cell.kernel.boot import compose_boot_script
    import types
    k = Kernel(boot_script=compose_boot_script([]))
    sleep = k.L["sleep"]
    assert isinstance(sleep, types.MethodType)  # bound method, not closure
    assert sleep.__self__ is k
    sleep()
    assert k.L["_sleeping"] is True


def test_sleep_survives_cloudpickle_roundtrip(tmp_path):
    """Bound methods pickle cleanly; closures over ns do not."""
    import cloudpickle, types
    from vessal.ark.shell.hull.cell.kernel import Kernel
    from vessal.ark.shell.hull.cell.kernel.boot import compose_boot_script
    k = Kernel(boot_script=compose_boot_script([]))
    assert k.L["_sleeping"] is False
    blob = cloudpickle.dumps(k.L)
    restored_ns = cloudpickle.loads(blob)
    sleep = restored_ns["sleep"]
    assert isinstance(sleep, types.MethodType)
    assert sleep.__self__.L is restored_ns
    sleep()
    assert restored_ns["_sleeping"] is True


def test_sleep_rebinds_after_restore(tmp_path):
    """After restore(), ns['sleep'] must be re-bound to the new Kernel."""
    from vessal.ark.shell.hull.cell.kernel import Kernel
    from vessal.ark.shell.hull.cell.kernel.boot import compose_boot_script
    k = Kernel(boot_script=compose_boot_script([]))
    snap = str(tmp_path / "snap.pkl")
    k.snapshot(snap)

    k2 = Kernel(boot_script=compose_boot_script([]))
    k2.restore(snap)
    sleep = k2.L["sleep"]
    assert sleep.__self__ is k2  # bound to k2, not k
    sleep()
    assert k2.L["_sleeping"] is True
