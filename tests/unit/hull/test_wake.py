"""tests/hull/unit/test_wake.py — _wake variable injection tests.

Verifies that EventLoop.inject_wake() and _frame_loop() correctly set the _wake variable.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from vessal.ark.shell.hull.event_loop import EventLoop


def _make_stub_cell(responses=None) -> MagicMock:
    """Construct a minimal Cell stub sufficient for _frame_loop() to start one frame and exit."""
    cell = MagicMock()
    ns: dict = {
        "_frame": 0,
        "_sleeping": False,
        "_wake": "",
        "_next_wake": None,
        "_context_pct": 0,
    }

    call_count = [0]
    if responses is None:
        responses = [True]  # default: set _sleeping=True on the first frame

    def fake_step(tracer=None):
        idx = call_count[0]
        call_count[0] += 1
        ns["_frame"] = ns.get("_frame", 0) + 1
        if idx < len(responses) and responses[idx]:
            ns["_sleeping"] = True
        result = MagicMock()
        result.protocol_error = "stub"
        return result

    cell.L = ns
    cell.step = fake_step
    return cell


class TestWakeInjection:
    """inject_wake() correctly sets ns['_wake'] at the start of run."""

    def test_inject_wake_sets_user_message(self):
        """inject_wake() sets ns['_wake'] = 'user_message'."""
        cell = _make_stub_cell()
        loop = EventLoop(cell=cell)
        loop.inject_wake({"reason": "user_message"})
        assert cell.L["_wake"] == "user_message"

    def test_wake_visible_during_frame_loop(self):
        """_wake is readable by cell.step during _frame_loop() execution."""
        cell = _make_stub_cell()
        wake_values: list[str] = []

        original_step = cell.step

        def capturing_step(tracer=None):
            wake_values.append(cell.L.get("_wake", "NOT_SET"))
            return original_step(tracer)

        cell.step = capturing_step
        loop = EventLoop(cell=cell, max_frames_per_wake=10)
        loop.inject_wake({"reason": "user_request"})
        loop._frame_loop()

        assert len(wake_values) >= 1
        assert wake_values[0] == "user_request"

    def test_inject_wake_clears_idle(self):
        """inject_wake() clears the _sleeping flag."""
        cell = _make_stub_cell()
        cell.L["_sleeping"] = True
        loop = EventLoop(cell=cell)
        loop.inject_wake({"reason": "heartbeat"})
        assert cell.L["_sleeping"] is False

    def test_inject_wake_default_reason(self):
        """Uses heartbeat when the event has no reason field."""
        cell = _make_stub_cell()
        loop = EventLoop(cell=cell)
        loop.inject_wake({})
        assert cell.L["_wake"] == "heartbeat"
