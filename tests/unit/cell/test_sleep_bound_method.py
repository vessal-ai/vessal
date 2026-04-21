def test_sleep_is_bound_method():
    from vessal.ark.shell.hull.cell.kernel import Kernel
    import types
    k = Kernel()
    sleep = k.ns["sleep"]
    assert isinstance(sleep, types.MethodType)  # bound method, not closure
    assert sleep.__self__ is k
    sleep()
    assert k.ns["_sleeping"] is True


def test_sleep_survives_cloudpickle_roundtrip(tmp_path):
    """Bound methods pickle cleanly; closures over ns do not."""
    import cloudpickle, types
    from vessal.ark.shell.hull.cell.kernel import Kernel
    k = Kernel()
    assert k.ns["_sleeping"] is False
    blob = cloudpickle.dumps(k.ns)
    restored_ns = cloudpickle.loads(blob)
    sleep = restored_ns["sleep"]
    assert isinstance(sleep, types.MethodType)
    sleep()
    assert restored_ns["_sleeping"] is True
