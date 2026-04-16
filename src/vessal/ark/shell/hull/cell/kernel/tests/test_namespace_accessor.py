from vessal.ark.shell.hull.cell.cell import Cell


def test_cell_get_set_keys():
    cell = Cell.__new__(Cell)  # skip __init__ (needs no LLM)
    from vessal.ark.shell.hull.cell.kernel import Kernel
    cell._kernel = Kernel()

    cell.set("foo", 42)
    assert cell.get("foo") == 42
    assert "foo" in cell.keys()


def test_cell_get_default():
    cell = Cell.__new__(Cell)
    from vessal.ark.shell.hull.cell.kernel import Kernel
    cell._kernel = Kernel()

    assert cell.get("nonexistent") is None
    assert cell.get("nonexistent", "default") == "default"


def test_get_reads_from_ns_directly():
    """get() retrieves values written via ns[] property."""
    cell = Cell.__new__(Cell)
    from vessal.ark.shell.hull.cell.kernel import Kernel
    cell._kernel = Kernel()

    cell.ns["injected"] = "value"
    assert cell.get("injected") == "value"


def test_keys_reflects_live_state():
    """keys() shows live namespace state."""
    cell = Cell.__new__(Cell)
    from vessal.ark.shell.hull.cell.kernel import Kernel
    cell._kernel = Kernel()

    before = len(list(cell.keys()))
    cell.set("new_key", "new_value")
    after = len(list(cell.keys()))

    assert after == before + 1
    assert "new_key" in cell.keys()
