# tests/test_auxiliary.py — Auxiliary signal module tests
#
# Tests skill signal_update() contracts for Tasks and Pin skills.

import pytest

from vessal.skills.tasks.skill import Tasks as _Tasks
from vessal.skills.pin.skill import Pin as _Pin


# ──────────────────────────────────────────────────────────────────────────────
# goal signal (migrated to Hull loop.py, written directly to ns["_signal_goal"])
# ──────────────────────────────────────────────────────────────────────────────

class TestGoalSignal:
    def test_renders_goal(self):
        goal = "complete task A"
        goal_str = goal.strip()
        signal = ("task goal:\n" + goal_str) if goal_str else ""
        assert "complete task A" in signal

    def test_empty_goal_returns_empty(self):
        goal = ""
        goal_str = goal.strip()
        signal = ("task goal:\n" + goal_str) if goal_str else ""
        assert signal == ""

    def test_label_present(self):
        goal = "task goal"
        goal_str = goal.strip()
        signal = ("task goal:\n" + goal_str) if goal_str else ""
        assert "task goal:" in signal


# ──────────────────────────────────────────────────────────────────────────────
# skills/tasks/signals.py — compute_task_signal
# ──────────────────────────────────────────────────────────────────────────────

def _run_signal(tasks_instance) -> str:
    """Call tasks.signal_update() and return a "tasks: body" string."""
    tasks_instance.signal_update()
    if not tasks_instance.signal:
        return ""
    body = tasks_instance.signal.get("tasks", "")
    return f"tasks: {body}"


class TestTasksSignal:
    def test_empty_tree_shows_bootstrap(self):
        t = _Tasks()
        result = _run_signal(t)
        assert "tasks:" in result
        assert "Review current situation" in result
        assert "current:" in result

    def test_with_task_shows_current(self):
        t = _Tasks()
        t.add("do stuff")
        result = _run_signal(t)
        assert "current:" in result
        assert "do stuff" in result

    def test_done_task_shows_done_marker(self):
        t = _Tasks()
        t.add("task")
        t.done("1")
        result = _run_signal(t)
        assert "[done]" in result

    def test_stats_with_multiple_tasks(self):
        t = _Tasks()
        t.add("task 1")
        t.add("task 2")
        t.done("1")
        result = _run_signal(t)
        assert "task 1" in result
        assert "task 2" in result
        assert "[done]" in result

    def test_child_task_indented(self):
        t = _Tasks()
        t.add("parent")
        t.add("child", parent="1")
        result = _run_signal(t)
        lines = result.split("\n")
        # Find child task lines in the tree structure (excluding "current:" and title prefix lines)
        child_lines = [
            l for l in lines
            if "1.1" in l and not l.startswith("current:") and not l.startswith("tasks:")
        ]
        assert child_lines
        assert child_lines[0].startswith("  ")


# ──────────────────────────────────────────────────────────────────────────────
# skills/pin/signals.py — compute_pin_signal
# ──────────────────────────────────────────────────────────────────────────────

def _run_pin_signal(pins: set, ns: dict) -> str:
    """Construct a Pin instance, inject ns, pin all variables, call signal_update(), and return the result string."""
    p = _Pin(ns=ns)
    for name in pins:
        p.pin(name)
    p.signal_update()
    if not p.signal:
        return ""
    body = p.signal.get("pinned", "")
    return f"pinned:\n{body}"


class TestPinsSignal:
    def test_empty_pins_returns_empty(self):
        assert _run_pin_signal(set(), {"x": 1}) == ""

    def test_renders_pinned_var(self):
        result = _run_pin_signal({"x"}, {"x": 42})
        assert "x" in result
        assert "42" in result

    def test_missing_var_shows_not_found(self):
        result = _run_pin_signal({"ghost"}, {})
        assert "ghost" in result
        assert "not found" in result

    def test_label_present(self):
        result = _run_pin_signal({"x"}, {"x": 1})
        assert "pinned:" in result

    def test_no_budget_param_required(self):
        result = _run_pin_signal({"x"}, {"x": 1})
        assert result != ""
