from vessal.ark.shell.hull.cell.cell import Cell


def test_set_gate_action():
    cell = Cell.__new__(Cell)
    from vessal.ark.shell.hull.cell.kernel import Kernel
    from vessal.ark.shell.hull.cell.gate import ActionGate, StateGate
    cell._kernel = Kernel()
    cell._action_gate = ActionGate(mode="auto")
    cell._state_gate = StateGate(mode="auto")

    # Custom gate that blocks everything
    def block_all(code: str):
        return False, "blocked by custom rule"

    cell.set_gate("action", block_all)
    result = cell._action_gate.check("print('hi')")
    assert not result.allowed


def test_set_gate_state():
    cell = Cell.__new__(Cell)
    from vessal.ark.shell.hull.cell.kernel import Kernel
    from vessal.ark.shell.hull.cell.gate import ActionGate, StateGate
    cell._kernel = Kernel()
    cell._action_gate = ActionGate(mode="auto")
    cell._state_gate = StateGate(mode="auto")

    def block_all(state: str):
        return False, "blocked"

    cell.set_gate("state", block_all)
    result = cell._state_gate.check("some state")
    assert not result.allowed


def test_set_gate_invalid_type():
    cell = Cell.__new__(Cell)
    from vessal.ark.shell.hull.cell.kernel import Kernel
    from vessal.ark.shell.hull.cell.gate import ActionGate, StateGate
    cell._kernel = Kernel()
    cell._action_gate = ActionGate(mode="auto")
    cell._state_gate = StateGate(mode="auto")

    import pytest

    with pytest.raises(ValueError, match="Unknown gate type"):
        cell.set_gate("invalid", lambda x: (True, ""))
