# tests/test_auxiliary.py — Auxiliary signal module tests
#
# Tests the render(ns) function for each module under signals/.
# Each module is tested independently.
#
# kernel/signals/ is the new implementation (no required budget parameter).

import pytest

from vessal.ark.shell.hull.cell.kernel.render.signals import (
    namespace_dir as k_namespace_dir,
    system_vars as k_system_vars,
    verdict as k_verdict,
)
from vessal.skills.tasks.skill import Tasks as _Tasks
from vessal.skills.pin.skill import Pin as _Pin

from vessal.ark.shell.hull.cell.protocol import Verdict, VerdictFailure


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
# kernel/signals/verdict.py (NEW)
# ──────────────────────────────────────────────────────────────────────────────

class TestVerdictSignal:
    def test_no_verdict_returns_empty(self):
        ns = {}
        assert k_verdict.render(ns) == ""

    def test_verdict_none_returns_empty(self):
        ns = {"verdict": None}
        assert k_verdict.render(ns) == ""

    def test_all_passed_no_failures(self):
        v = Verdict(total=3, passed=3, failures=())
        ns = {"verdict": v}
        result = k_verdict.render(ns)
        assert "3/3" in result
        assert "assertions passed" in result

    def test_partial_pass_shown(self):
        v = Verdict(total=4, passed=2, failures=(
            VerdictFailure(kind="assertion_failed", assertion="assert x == 1", message="x was 0"),
            VerdictFailure(kind="assertion_failed", assertion="assert y > 0", message="y was -1"),
        ))
        ns = {"verdict": v}
        result = k_verdict.render(ns)
        assert "2/4" in result

    def test_failures_shown(self):
        failure = VerdictFailure(
            kind="assertion_failed",
            assertion="assert x == 1",
            message="x was 0",
        )
        v = Verdict(total=1, passed=0, failures=(failure,))
        ns = {"verdict": v}
        result = k_verdict.render(ns)
        assert "assertion_failed" in result
        assert "assert x == 1" in result
        assert "x was 0" in result

    def test_failure_format(self):
        failure = VerdictFailure(
            kind="assertion_failed",
            assertion="assert z",
            message="z is False",
        )
        v = Verdict(total=1, passed=0, failures=(failure,))
        ns = {"verdict": v}
        result = k_verdict.render(ns)
        # Format: [kind] assertion — message
        assert "[assertion_failed]" in result
        assert "—" in result

    def test_no_failure_section_when_all_pass(self):
        v = Verdict(total=2, passed=2, failures=())
        ns = {"verdict": v}
        result = k_verdict.render(ns)
        # No failure lines when no failures
        lines = result.splitlines()
        assert len(lines) == 1  # only summary line


# ──────────────────────────────────────────────────────────────────────────────
# kernel/signals/namespace_dir.py
# ──────────────────────────────────────────────────────────────────────────────

class TestNamespaceDirSignal:
    def test_renders_user_vars(self):
        ns = {"x": 42, "_frame": 1}
        result = k_namespace_dir.render(ns)
        assert "x" in result
        assert "int" in result

    def test_excludes_system_vars(self):
        ns = {"_frame": 1, "_progress": "p", "result": "done"}
        result = k_namespace_dir.render(ns)
        assert "_frame" not in result
        assert "_progress" not in result
        assert "result" in result

    def test_excludes_builtin_names(self):
        ns = {"load": lambda: None, "_builtin_names": ["load"]}
        result = k_namespace_dir.render(ns)
        assert "load" not in result

    def test_empty_namespace(self):
        ns = {"_frame": 1, "_builtin_names": []}
        result = k_namespace_dir.render(ns)
        assert "(empty)" in result

    def test_label_present(self):
        ns = {"x": 1}
        result = k_namespace_dir.render(ns)
        assert "x:" in result  # variable name shown

    def test_no_budget_param_required(self):
        ns = {"x": 1}
        result = k_namespace_dir.render(ns)
        assert result != ""


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


# ──────────────────────────────────────────────────────────────────────────────
# kernel/signals/system_vars.py
# ──────────────────────────────────────────────────────────────────────────────

class TestSystemVarsSignal:
    def test_renders_frame_number(self):
        ns = {"_frame": 42}
        result = k_system_vars.render(ns)
        assert "42" in result

    def test_always_returns_string(self):
        result = k_system_vars.render({})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_no_budget_param_required(self):
        ns = {"_frame": 1}
        result = k_system_vars.render(ns)
        assert result != ""


