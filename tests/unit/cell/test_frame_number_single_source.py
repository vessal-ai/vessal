# test_frame_number_single_source.py — verify ns["_frame"] increments exactly once per step

from unittest.mock import MagicMock, patch

from vessal.ark.shell.hull.cell import Cell
from vessal.ark.shell.hull.cell.protocol import Action, Ping, Pong, State


def _make_cell(**kwargs) -> Cell:
    with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI"):
        return Cell(**kwargs)


def _fixed_pong(code: str = "pass") -> Pong:
    return Pong(think="", action=Action(operation=code, expect=""))


def _stub_core(cell: Cell, pong: Pong) -> None:
    """Replace cell._core.step with a stub that returns a fixed Pong."""
    cell._core.step = MagicMock(return_value=(pong, None, None))


def test_ns_frame_increments_exactly_once_per_step():
    """ns["_frame"] must go from N to N+1 exactly once per step, via _commit_frame."""
    cell = _make_cell()
    _stub_core(cell, _fixed_pong("x = 1"))

    initial = cell.L["_frame"]
    result = cell.step()

    assert result.protocol_error is None
    assert cell.L["_frame"] == initial + 1


def test_ns_frame_increments_exactly_once_over_multiple_steps():
    """After N steps, ns["_frame"] == N (from initial 0)."""
    cell = _make_cell()
    _stub_core(cell, _fixed_pong("pass"))

    for step_n in range(1, 4):
        cell._core.step = MagicMock(return_value=(_fixed_pong("pass"), None, None))
        result = cell.step()
        assert result.protocol_error is None
        assert cell.L["_frame"] == step_n


def test_ns_frame_not_incremented_on_core_error():
    """ns["_frame"] must not change when core.step raises an exception."""
    cell = _make_cell()
    cell._core.step = MagicMock(side_effect=RuntimeError("network failure"))

    initial = cell.L["_frame"]
    result = cell.step()

    assert result.protocol_error is not None
    assert cell.L["_frame"] == initial


def test_frame_number_passed_to_core_equals_ns_frame_plus_one():
    """Core.step receives frame_number == ns["_frame"] + 1 (the about-to-be-committed number)."""
    cell = _make_cell()
    pong = _fixed_pong("pass")
    received_frames: list[int] = []

    def _capture_frame(ping, tracer, frame):
        received_frames.append(frame)
        return (pong, None, None)

    cell._core.step = MagicMock(side_effect=_capture_frame)

    initial = cell.L["_frame"]
    cell.step()

    assert len(received_frames) == 1
    assert received_frames[0] == initial + 1


def test_ns_frame_write_is_single_source_commit_frame():
    """ns["_frame"] must not be written by executor mid-step.

    The write must happen exactly once, in _commit_frame, AFTER execution.
    Verifies that ns["_frame"] is still equal to initial immediately after the
    executor returns — before _commit_frame runs.
    """
    import vessal.ark.shell.hull.cell.kernel.kernel as kernel_mod
    from vessal.ark.shell.hull.cell.kernel.executor import execute as real_execute

    cell = _make_cell()
    pong = _fixed_pong("pass")
    cell._core.step = MagicMock(return_value=(pong, None, None))

    initial = cell.L["_frame"]
    frame_after_execute: list[int] = []

    def _tracking_execute(operation, G, L, frame_number):
        result = real_execute(operation, G, L, frame_number)
        # Capture L["_frame"] immediately after execute() returns,
        # before _commit_frame has a chance to write it.
        frame_after_execute.append(L["_frame"])
        return result

    with patch.object(kernel_mod, "execute", side_effect=_tracking_execute):
        cell.step()

    # After step: ns["_frame"] must equal initial + 1
    assert cell.L["_frame"] == initial + 1
    # Immediately after executor returned (before _commit_frame): must still be initial
    assert len(frame_after_execute) == 1
    assert frame_after_execute[0] == initial, (
        f"executor wrote ns['_frame'] mid-step: expected {initial}, got {frame_after_execute[0]}"
    )
