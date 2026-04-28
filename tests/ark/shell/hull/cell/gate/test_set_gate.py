import pytest

from vessal.ark.shell.hull.cell.cell import Cell
from vessal.ark.shell.hull.cell.gate import ActionGate, StateGate
from vessal.ark.shell.hull.cell.kernel import Kernel
from vessal.ark.shell.hull.cell.kernel.boot import compose_boot_script


def _make_cell() -> Cell:
    cell = Cell.__new__(Cell)
    cell._kernel = Kernel(boot_script=compose_boot_script([]))
    cell._action_gate = ActionGate(mode="auto")
    cell._state_gate = StateGate(mode="auto")
    return cell


def test_set_gate_action():
    cell = _make_cell()

    def block_all(code: str):
        return False, "blocked by custom rule"

    cell.set_gate("action", block_all)
    result = cell._action_gate.check("print('hi')")
    assert not result.allowed


def test_set_gate_state():
    cell = _make_cell()

    def block_all(state: str):
        return False, "blocked"

    cell.set_gate("state", block_all)
    result = cell._state_gate.check("some state")
    assert not result.allowed


def test_set_gate_invalid_type():
    cell = _make_cell()

    with pytest.raises(ValueError, match="Unknown gate type"):
        cell.set_gate("invalid", lambda x: (True, ""))
