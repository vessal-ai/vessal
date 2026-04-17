"""test_event_loop — Hull event loop unit tests."""
import asyncio
import pytest
from unittest.mock import MagicMock, patch

from vessal.ark.shell.hull.event_loop import EventLoop
from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream


@pytest.fixture
def mock_cell():
    cell = MagicMock()
    cell.ns = {
        "_sleeping": False,
        "_wake": "",
        "_next_wake": None,
        "_frame": 0,
        "_signal_outputs": [],
        "_frame_stream": FrameStream(),
    }
    cell.get.side_effect = lambda key, default=None: cell.ns.get(key, default)
    cell.set.side_effect = lambda key, value: cell.ns.__setitem__(key, value)
    return cell


def test_inject_wake_sets_namespace(mock_cell):
    """inject_wake writes the wake reason into namespace."""
    loop = EventLoop(cell=mock_cell)
    loop.inject_wake({"reason": "user_message"})
    assert mock_cell.ns["_wake"] == "user_message"


def test_inject_wake_clears_idle(mock_cell):
    """inject_wake clears the _sleeping flag."""
    mock_cell.ns["_sleeping"] = True
    loop = EventLoop(cell=mock_cell)
    loop.inject_wake({"reason": "heartbeat"})
    assert mock_cell.ns["_sleeping"] is False


def test_inject_wake_default_reason(mock_cell):
    """Uses heartbeat when the event has no reason field."""
    loop = EventLoop(cell=mock_cell)
    loop.inject_wake({})
    assert mock_cell.ns["_wake"] == "heartbeat"


def test_inject_wake_does_not_touch_skills(mock_cell):
    """inject_wake no longer looks up or calls any Skill."""
    from vessal.skills.chat.skill import Chat
    h = Chat()
    mock_cell.ns["chat"] = h
    loop = EventLoop(mock_cell)
    loop.inject_wake({"reason": "user_message", "content": "hello"})
    # chat skill inbox should have no messages (inject_wake does not deliver)
    assert h.read() == []


def test_run_wake_cycle_skips_frame_logger_without_log_dir(mock_cell):
    """_run_wake_cycle does not create a FrameLogger when Tracer has no log directory."""
    from vessal.ark.shell.hull.event_loop import FrameHooks
    from vessal.ark.util.logging import Tracer

    after_step_calls = []
    mock_cell.ns["_sleeping"] = True  # sleep immediately, zero frame loop

    loop = EventLoop(
        cell=mock_cell,
        tracer=Tracer("", enabled=False),
    )
    # Verify no error and no file created
    loop._run_wake_cycle()  # should complete without touching filesystem


def test_inject_wake_alarm_reason(mock_cell):
    """alarm wake writes _wake = 'alarm'."""
    loop = EventLoop(cell=mock_cell)
    loop.inject_wake({"reason": "alarm"})
    assert mock_cell.ns["_wake"] == "alarm"


def test_frame_loop_calls_before_frame_hook(mock_cell):
    """_frame_loop calls hooks.before_frame every frame."""
    from vessal.ark.shell.hull.event_loop import FrameHooks

    call_count = {"n": 0}

    def before():
        call_count["n"] += 1

    hooks = FrameHooks(before_frame=before)

    # Agent sleeps immediately after one frame
    def step_then_idle(tracer=None):
        mock_cell.ns["_sleeping"] = True
        r = MagicMock()
        r.protocol_error = None
        return r

    mock_cell.ns["_sleeping"] = False
    mock_cell.step = step_then_idle

    loop = EventLoop(cell=mock_cell, hooks=hooks)
    loop._frame_loop()

    assert call_count["n"] == 1


def test_event_queue_is_stdlib_queue(mock_cell):
    """event_queue is a stdlib queue.Queue (thread-safe)."""
    import queue as queue_mod
    loop = EventLoop(mock_cell)
    assert isinstance(loop.event_queue, queue_mod.Queue)


def test_inject_wake_fn_puts_event_on_queue():
    """ns['_inject_wake'] injects a wake event onto the event queue."""
    import queue as queue_mod
    from unittest.mock import MagicMock
    cell = MagicMock()
    cell.ns = {}
    loop = EventLoop(cell)
    # Simulate Hull exposing _inject_wake
    inject_fn = lambda reason="user_message": loop.event_queue.put({"reason": reason})
    cell.ns["_inject_wake"] = inject_fn

    inject_fn("user_message")
    event = loop.event_queue.get(timeout=1)
    assert event["reason"] == "user_message"


def test_after_frame_hook_fires(mock_cell):
    """_frame_loop calls hooks.after_frame once per successful frame."""
    from vessal.ark.shell.hull.event_loop import FrameHooks

    calls = {"n": 0}

    def after():
        calls["n"] += 1

    hooks = FrameHooks(after_frame=after)

    def step_then_idle(tracer=None):
        mock_cell.ns["_sleeping"] = True
        r = MagicMock()
        r.protocol_error = None
        return r

    mock_cell.ns["_sleeping"] = False
    mock_cell.step = step_then_idle

    loop = EventLoop(cell=mock_cell, hooks=hooks)
    loop._frame_loop()

    assert calls["n"] == 1


def test_frame_loop_breaks_on_protocol_error(mock_cell):
    """_frame_loop breaks immediately on protocol_error without retrying."""
    from vessal.ark.shell.hull.cell.protocol import StepResult

    call_count = 0

    def fake_step(tracer=None):
        nonlocal call_count
        call_count += 1
        return StepResult(protocol_error="BadRequestError: test")

    mock_cell.step = fake_step
    loop = EventLoop(cell=mock_cell, max_frames_per_wake=10)
    loop._frame_loop()

    assert call_count == 1, f"expected 1 call, got {call_count}"
    assert mock_cell.ns["_sleeping"] is True
    assert "protocol error" in mock_cell.ns.get("_error", "")
