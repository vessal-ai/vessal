# test_ping_pong_projection.py — verify that cell.ping/pong are projections of frame_stream
#
# The invariant: after step(), cell.ping and cell.pong must equal the values stored
# in the latest hot frame of _frame_stream, not the pre-commit in-memory copies.
# This guards against Cell holding stale copies if the frame record ever diverges.

from unittest.mock import MagicMock, patch

from vessal.ark.shell.hull.cell import Cell
from vessal.ark.shell.hull.cell.protocol import Action, Ping, Pong, State


def _make_cell(**kwargs) -> Cell:
    with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI"):
        return Cell(**kwargs)


def _fixed_pong(code: str = "pass") -> Pong:
    return Pong(think="my-think", action=Action(operation=code, expect="my-expect"))


def _stub_core(cell: Cell, pong: Pong) -> None:
    cell._core.step = MagicMock(return_value=(pong, None, None))


def test_ping_is_fresh_after_step():
    """cell.ping after step() is the Ping for the next frame, rendered by kernel.ping() post-commit.

    Verifies that cell._ping is not stale from pre-step state: it reflects the namespace
    after the current frame was committed and rendered.
    """
    cell = _make_cell()
    cell.L["_system_prompt"] = "BEFORE_STEP"
    pong = _fixed_pong("x = 1")
    _stub_core(cell, pong)

    # Inject a namespace mutation that should show up in the post-step Ping
    cell.L["_system_prompt"] = "AFTER_COMMIT_PROMPT"

    result = cell.step()
    assert result.protocol_error is None

    # cell.ping is the Ping produced by kernel.ping() after execution — fresh, not stale
    assert cell.ping is not None
    assert isinstance(cell.ping, Ping)
    assert cell.ping.system_prompt == "AFTER_COMMIT_PROMPT"


def test_pong_is_set_after_step():
    """cell.pong after step() is the Pong returned by core.step() for that frame."""
    cell = _make_cell()
    pong = _fixed_pong("y = 2")
    _stub_core(cell, pong)

    result = cell.step()
    assert result.protocol_error is None

    assert cell.pong is not None
    assert cell.pong.action.operation == "y = 2"


def test_ping_pong_consistent_across_multiple_steps():
    """After each step, cell.ping/pong must reflect the latest committed frame."""
    cell = _make_cell()

    for i in range(1, 4):
        pong = _fixed_pong(f"x_{i} = {i}")
        _stub_core(cell, pong)
        result = cell.step()
        assert result.protocol_error is None

        fs = cell.L["_frame_stream"]
        latest = fs.latest_hot_frame()
        assert latest is not None
        assert latest["number"] == i

        frame_pong_dict = latest.get("pong")
        assert cell.pong.action.operation == frame_pong_dict.get("action", {}).get("operation", "")

        frame_ping_dict = latest.get("ping")
        assert cell.ping.system_prompt == frame_ping_dict.get("system_prompt", "")
