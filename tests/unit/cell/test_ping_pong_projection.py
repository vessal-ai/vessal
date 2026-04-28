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


def test_ping_is_frame_stream_projection():
    """cell.ping must be re-derived from frame_stream after step(), not retained from prepare().

    We simulate a divergence: after kernel.step() commits the frame, we overwrite the
    frame's ping in the stream with a sentinel value. If cell.ping is truly a projection,
    it will reflect the sentinel. If cell.ping is just the pre-commit cached value, it won't.
    """
    cell = _make_cell()
    pong = _fixed_pong("x = 1")
    _stub_core(cell, pong)

    import vessal.ark.shell.hull.cell.kernel.kernel as kernel_mod

    sentinel_system_prompt = "SENTINEL_PING"
    original_commit = kernel_mod.Kernel._commit_frame

    def _patched_commit(self, pong_arg, observation, frame_number, ping=None):
        original_commit(self, pong_arg, observation, frame_number, ping=ping)
        # After the real commit, overwrite the frame's ping in the stream
        fs = self.L.get("_frame_stream")
        latest = fs.latest_hot_frame() if fs is not None else None
        if latest is not None:
            latest["ping"] = {
                "system_prompt": sentinel_system_prompt,
                "state": {"frame_stream": "", "signals": ""},
            }

    with patch.object(kernel_mod.Kernel, "_commit_frame", _patched_commit):
        result = cell.step()

    assert result.protocol_error is None

    # If cell.ping is a projection from frame_stream, it must reflect the sentinel
    assert cell.ping is not None
    assert cell.ping.system_prompt == sentinel_system_prompt, (
        f"cell.ping.system_prompt should be {sentinel_system_prompt!r} "
        f"(frame_stream projection), got {cell.ping.system_prompt!r}. "
        "This means _ping is still the pre-commit cached value, not a projection."
    )


def test_pong_is_frame_stream_projection():
    """cell.pong must be re-derived from frame_stream after step(), not retained from core.step().

    We simulate a divergence: after kernel.step() commits the frame, we overwrite the
    frame's pong in the stream with a sentinel. If cell.pong is truly a projection,
    it will reflect the sentinel. If it's just the pre-commit Pong, it won't.
    """
    cell = _make_cell()
    pong = _fixed_pong("y = 2")
    _stub_core(cell, pong)

    import vessal.ark.shell.hull.cell.kernel.kernel as kernel_mod

    sentinel_operation = "SENTINEL_PONG"
    original_commit = kernel_mod.Kernel._commit_frame

    def _patched_commit(self, pong_arg, observation, frame_number, ping=None):
        original_commit(self, pong_arg, observation, frame_number, ping=ping)
        fs = self.L.get("_frame_stream")
        latest = fs.latest_hot_frame() if fs is not None else None
        if latest is not None:
            latest["pong"] = {
                "think": "",
                "action": {"operation": sentinel_operation, "expect": ""},
            }

    with patch.object(kernel_mod.Kernel, "_commit_frame", _patched_commit):
        result = cell.step()

    assert result.protocol_error is None

    assert cell.pong is not None
    assert cell.pong.action.operation == sentinel_operation, (
        f"cell.pong.action.operation should be {sentinel_operation!r} "
        f"(frame_stream projection), got {cell.pong.action.operation!r}. "
        "This means _pong is still the pre-commit cached value, not a projection."
    )


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
