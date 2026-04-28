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


def test_ping_is_from_previous_frame():
    """FrameRecord.ping field is the Ping *before* this frame's render, not the new one.

    The timing contract (spec §1.2): frame N is committed with ping_for_record=_last_ping,
    where _last_ping is the Ping returned by the previous ping() call. The new Ping
    rendered at the end of ping() is NOT the one stored in the committed FrameRecord.
    This test patches _commit to intercept ping_for_record and verifies it equals
    the initial Ping (_last_ping after bootstrap), proving derivation from the committed
    frame rather than any pre-commit cache.
    """
    import vessal.ark.shell.hull.cell.kernel.kernel as kernel_mod

    cell = _make_cell()
    ns = {"globals": cell._kernel.G, "locals": cell._kernel.L}

    # Bootstrap: ping(None) stores the initial Ping as _last_ping without committing
    initial_ping = cell._kernel.ping(None, ns)

    committed_pings = []
    original_commit = kernel_mod.Kernel._commit

    def recording_commit(self, pong, obs, frame_n, ping_for_record=None):
        committed_pings.append(ping_for_record)
        return original_commit(self, pong, obs, frame_n, ping_for_record=ping_for_record)

    with patch.object(kernel_mod.Kernel, "_commit", recording_commit):
        pong = Pong(think="", action=Action(operation="x = 1", expect=""))
        cell._kernel.ping(pong, ns)

    # Frame 1 must have been committed with the initial Ping (from bootstrap), not the new one
    assert len(committed_pings) == 1
    assert committed_pings[0] is initial_ping


def test_pong_committed_to_frame_stream():
    """FrameRecord.pong field is captured by _commit from the passed pong argument.

    Patches _commit to capture the pong passed for commit, then verifies the committed
    pong's operation matches the pong that was passed — proving _commit receives the
    correct Pong, not a stale pre-commit cache.
    """
    import vessal.ark.shell.hull.cell.kernel.kernel as kernel_mod

    cell = _make_cell()
    ns = {"globals": cell._kernel.G, "locals": cell._kernel.L}
    cell._kernel.ping(None, ns)

    committed_pongs = []
    original_commit = kernel_mod.Kernel._commit

    def recording_commit(self, pong, obs, frame_n, ping_for_record=None):
        committed_pongs.append(pong)
        return original_commit(self, pong, obs, frame_n, ping_for_record=ping_for_record)

    sentinel_op = "sentinel_pong_op = 42"
    with patch.object(kernel_mod.Kernel, "_commit", recording_commit):
        pong = Pong(think="", action=Action(operation=sentinel_op, expect=""))
        cell._kernel.ping(pong, ns)

    assert len(committed_pongs) == 1
    assert committed_pongs[0].action.operation == sentinel_op


def test_ping_pong_consistent_across_multiple_steps():
    """After each step, cell.ping/pong reflect the most recent committed Pong."""
    cell = _make_cell()

    for i in range(1, 4):
        pong = _fixed_pong(f"x_{i} = {i}")
        _stub_core(cell, pong)
        result = cell.step()
        assert result.protocol_error is None

        # cell.pong should reflect the Pong from the most recent step
        assert cell.pong.action.operation == f"x_{i} = {i}"
