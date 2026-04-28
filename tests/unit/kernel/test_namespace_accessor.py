from vessal.ark.shell.hull.cell.cell import Cell
from tests.unit.kernel._ping_helpers import minimal_kernel


def test_cell_L_set_get_keys():
    cell = Cell.__new__(Cell)  # skip __init__ (needs no LLM)
    cell._kernel = minimal_kernel()

    cell.L["foo"] = 42
    assert cell.L.get("foo") == 42
    assert "foo" in cell.L.keys()


def test_cell_L_get_default():
    cell = Cell.__new__(Cell)
    cell._kernel = minimal_kernel()

    assert cell.L.get("nonexistent") is None
    assert cell.L.get("nonexistent", "default") == "default"


def test_L_reads_writes_directly():
    """L is a dict; reads/writes go directly to the kernel local namespace."""
    cell = Cell.__new__(Cell)
    cell._kernel = minimal_kernel()

    cell.L["injected"] = "value"
    assert cell.L["injected"] == "value"


def test_L_keys_reflects_live_state():
    """L.keys() shows live namespace state."""
    cell = Cell.__new__(Cell)
    cell._kernel = minimal_kernel()

    before = len(list(cell.L.keys()))
    cell.L["new_key"] = "new_value"
    after = len(list(cell.L.keys()))

    assert after == before + 1
    assert "new_key" in cell.L.keys()
