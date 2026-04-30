"""Verify EventLoop calls compaction_cell.step() iff should_compact is true."""

from unittest.mock import MagicMock


def _make_main_cell_mock():
    """Return a MagicMock that behaves like a Cell for EventLoop's _frame_loop."""
    from vessal.cell.protocol import StepResult
    from vessal.skills.system.skill import System

    class _FakeKernel:
        def __init__(self):
            self.L: dict = {"_frame": 0, "signals": {}}

    fk = _FakeKernel()
    sys_skill = System()
    sys_skill._bind_kernel(fk)
    sys_skill.wake()

    cell = MagicMock()
    cell.L = fk.L
    cell.G = {"_system": sys_skill}

    step_calls = {"n": 0}

    def step_then_sleep(tracer=None):
        step_calls["n"] += 1
        sys_skill._sleeping = True
        return StepResult()

    cell.step = step_then_sleep
    cell._step_calls = step_calls
    return cell


def test_compaction_step_called_when_trigger_true(monkeypatch):
    from vessal.hull.event_loop import EventLoop

    main_cell = _make_main_cell_mock()
    compaction_cell = MagicMock()

    monkeypatch.setattr(
        "vessal.hull.event_loop.should_compact",
        lambda path, k=4: True,
    )

    loop = EventLoop(
        main_cell=main_cell,
        compaction_cell=compaction_cell,
        main_db_path="ignored.db",
        max_frames_per_wake=1,
    )
    loop._run_wake_cycle()

    assert main_cell._step_calls["n"] == 1
    compaction_cell.step.assert_called_once()


def test_compaction_step_skipped_when_trigger_false(monkeypatch):
    from vessal.hull.event_loop import EventLoop

    main_cell = _make_main_cell_mock()
    compaction_cell = MagicMock()

    monkeypatch.setattr(
        "vessal.hull.event_loop.should_compact",
        lambda path, k=4: False,
    )

    loop = EventLoop(
        main_cell=main_cell,
        compaction_cell=compaction_cell,
        main_db_path="ignored.db",
        max_frames_per_wake=1,
    )
    loop._run_wake_cycle()

    compaction_cell.step.assert_not_called()
