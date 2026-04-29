"""tests/hull/unit/test_wake.py — wake variable injection tests.

Verifies that EventLoop.inject_wake() and _frame_loop() correctly set the wake reason
on G["_system"]._wake_reason (spec §6.2).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from vessal.ark.shell.hull.event_loop import EventLoop
from vessal.skills.system import SystemSkill


def _make_stub_cell(responses=None) -> MagicMock:
    """Construct a minimal Cell stub sufficient for _frame_loop() to start one frame and exit."""
    cell = MagicMock()
    ns: dict = {
        "_frame": 0,
    }

    class _FakeKernel:
        def __init__(self):
            self.L = ns

    system_skill = SystemSkill()
    system_skill._bind_kernel(_FakeKernel())

    call_count = [0]
    if responses is None:
        responses = [True]  # default: call system_skill.sleep() on the first frame

    def fake_step(tracer=None):
        idx = call_count[0]
        call_count[0] += 1
        ns["_frame"] = ns.get("_frame", 0) + 1
        if idx < len(responses) and responses[idx]:
            system_skill.sleep()
        result = MagicMock()
        result.protocol_error = "stub"
        return result

    cell.L = ns
    cell.G = {"_system": system_skill}
    cell.step = fake_step
    return cell


class TestWakeInjection:
    """inject_wake() correctly records wake reason on G['_system']._wake_reason (spec §6.2)."""

    def test_inject_wake_sets_user_message(self):
        """inject_wake() records 'user_message' on _system._wake_reason."""
        cell = _make_stub_cell()
        loop = EventLoop(cell=cell)
        loop.inject_wake({"reason": "user_message"})
        assert cell.G["_system"]._wake_reason == "user_message"

    def test_wake_visible_during_frame_loop(self):
        """_wake_reason is readable from G['_system'] during _frame_loop() execution."""
        cell = _make_stub_cell()
        wake_values: list[str] = []

        original_step = cell.step

        def capturing_step(tracer=None):
            wake_values.append(cell.G["_system"]._wake_reason)
            return original_step(tracer)

        cell.step = capturing_step
        loop = EventLoop(cell=cell, max_frames_per_wake=10)
        loop.inject_wake({"reason": "user_request"})
        loop._frame_loop()

        assert len(wake_values) >= 1
        assert wake_values[0] == "user_request"

    def test_inject_wake_clears_idle(self):
        """inject_wake() clears the _sleeping flag on the _system Skill."""
        cell = _make_stub_cell()
        cell.G["_system"]._sleeping = True
        loop = EventLoop(cell=cell)
        loop.inject_wake({"reason": "heartbeat"})
        assert cell.G["_system"]._sleeping is False

    def test_inject_wake_default_reason(self):
        """Uses heartbeat when the event has no reason field."""
        cell = _make_stub_cell()
        loop = EventLoop(cell=cell)
        loop.inject_wake({})
        assert cell.G["_system"]._wake_reason == "heartbeat"
