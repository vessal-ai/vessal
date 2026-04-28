# tests/unit/kernel/test_kernel.py — Kernel unit tests
#
# Test coverage:
#   TestIsUserVar       is_user_var helper function
#   TestExecute         execute() — execute code, side effects written to ns
#   TestKernel          Kernel class integration tests (including ns exposure, render method)
import inspect
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vessal.ark.shell.hull.cell.kernel import Kernel

from vessal.ark.shell.hull.cell.kernel.executor import ExecResult, is_user_var, execute, _maybe_capture_last_expr
from vessal.ark.shell.hull.skill_loader import SkillLoader


from tests.unit.kernel._ping_helpers import _ns, _exec, minimal_kernel

# ─────────────────────────────────────────────
# Helper: construct a minimal namespace (without defaults)
# ─────────────────────────────────────────────

def bare_ns() -> dict:
    """Return an empty namespace without defaults, containing only minimal system variables (v3 format).

    Used to isolate tests for execute without any side effects from defaults.
    """
    return {
        "_frame": 0,
        "_plan": "",
        "_builtin_names": [],
        "_operation": "",
        "_stdout": "",
        "_error": None,
        "_diff": "",
        "_context_budget": 128000,
        "_token_budget": 4096,
        "_pins": set(),
        "_log_path": "",
        "_context_pct": 0,
        "_ns_meta": {},
        "_progress": "",
    }


def _kw() -> "Kernel":
    """Create Kernel with minimal namespace setup (test helper)."""
    k = minimal_kernel()
    k.L["_builtin_names"] = []
    return k


# ─────────────────────────────────────────────
# is_user_var
# ─────────────────────────────────────────────

class TestIsUserVar:
    def test_regular_name(self):
        assert is_user_var("x") is True

    def test_underscore_prefix(self):
        assert is_user_var("_x") is False

    def test_double_underscore(self):
        assert is_user_var("__init__") is False

    def test_empty_string(self):
        assert is_user_var("") is True  # empty string does not start with _

    def test_underscore_only(self):
        assert is_user_var("_") is False

    def test_long_user_name(self):
        assert is_user_var("my_long_variable_name") is True


# ─────────────────────────────────────────────
# executor.execute
# ─────────────────────────────────────────────

class TestExecute:
    def test_empty_action_returns_empty_exec_result(self):
        """Empty operation returns ExecResult with empty fields; no code is executed."""
        ns = bare_ns()
        result = execute("", {}, ns, frame_number=2)
        assert isinstance(result, ExecResult)
        assert result.stdout == ""
        assert result.error is None
        assert result.diff == ""

    def test_whitespace_action_treated_as_empty(self):
        ns = bare_ns()
        result = execute("   \n  ", {}, ns, frame_number=1)
        assert result.stdout == ""
        assert result.error is None

    def test_none_action_treated_as_empty(self):
        ns = bare_ns()
        result = execute(None, {}, ns, frame_number=1)
        assert result.error is None

    def test_returns_exec_result(self):
        """execute returns an ExecResult."""
        ns = bare_ns()
        result = execute("x = 1", {}, ns, frame_number=1)
        assert isinstance(result, ExecResult)

    def test_operation_does_not_pollute_ns(self):
        """execute() does not write _operation to ns; side-effect keys are not scattered."""
        ns = bare_ns()
        code = "x = 42"
        # _operation is pre-populated in bare_ns; execute should not overwrite it
        ns["_operation"] = "old"
        execute(code, {}, ns, frame_number=1)
        # execute() no longer writes _operation back; ns still has old value
        assert ns["_operation"] == "old"

    def test_simple_assignment(self):
        ns = bare_ns()
        result = execute("x = 42", {}, ns, frame_number=1)
        assert ns["x"] == 42
        assert result.error is None

    def test_stdout_captured(self):
        ns = bare_ns()
        result = execute("print('hello world')", {}, ns, frame_number=1)
        assert result.stdout == "hello world\n"
        assert result.error is None

    def test_multiple_prints(self):
        ns = bare_ns()
        result = execute("print('a')\nprint('b')", {}, ns, frame_number=1)
        assert "a\n" in result.stdout
        assert "b\n" in result.stdout

    def test_stdout_empty_when_no_print(self):
        ns = bare_ns()
        result = execute("x = 1", {}, ns, frame_number=1)
        assert result.stdout == ""

    def test_runtime_error_captured(self):
        ns = bare_ns()
        result = execute("1 / 0", {}, ns, frame_number=1)
        assert isinstance(result.error, ZeroDivisionError)

    def test_syntax_error_captured(self):
        ns = bare_ns()
        result = execute("def foo(:\n    pass", {}, ns, frame_number=1)
        assert isinstance(result.error, SyntaxError)

    def test_name_error_captured(self):
        ns = bare_ns()
        result = execute("y = undefined_var", {}, ns, frame_number=1)
        assert isinstance(result.error, NameError)

    def test_error_none_on_success(self):
        ns = bare_ns()
        result = execute("x = 1", {}, ns, frame_number=1)
        assert result.error is None

    def test_no_builtins_pollution(self):
        """__builtins__ injected by exec should be cleaned up."""
        ns = bare_ns()
        execute("x = 1", {}, ns, frame_number=1)
        assert "__builtins__" not in ns

    def test_diff_added(self):
        ns = bare_ns()
        result = execute("a = 1\nb = 'hello'", {}, ns, frame_number=1)
        assert "+a = 1" in result.diff
        assert "+b = hello" in result.diff

    def test_diff_modified(self):
        ns = bare_ns()
        execute("x = 1", {}, ns, frame_number=1)
        result = execute("x = 99", {}, ns, frame_number=2)
        assert "-x = 1" in result.diff
        assert "+x = 99" in result.diff

    def test_diff_deleted(self):
        ns = bare_ns()
        execute("x = 1", {}, ns, frame_number=1)
        result = execute("del x", {}, ns, frame_number=2)
        assert "-x = 1" in result.diff

    def test_diff_ignores_system_vars(self):
        """Variables starting with _ do not participate in diff."""
        ns = bare_ns()
        result = execute("_observe = ['x']", {}, ns, frame_number=1)
        assert result.diff == ""

    def test_diff_empty_when_no_change(self):
        ns = bare_ns()
        result = execute("pass", {}, ns, frame_number=1)
        assert result.diff == ""

    def test_history_not_managed_by_execute(self):
        """executor does not write _frame_stream; frame logging is managed by Cell via SQLite."""
        ns = bare_ns()
        execute("x = 1", {}, ns, frame_number=1)
        execute("y = 2", {}, ns, frame_number=2)
        assert "_frame_stream" not in ns

    def test_source_function_on_object(self):
        """Function source is recoverable via inspect.getsource (linecache)."""
        ns = bare_ns()
        code = "def add(a, b):\n    return a + b"
        execute(code, {}, ns, frame_number=1)
        src = inspect.getsource(ns["add"])
        assert "def add(a, b):" in src
        assert "return a + b" in src

    def test_source_class_on_object(self):
        """Class source is recoverable via inspect.getsource (linecache)."""
        ns = bare_ns()
        code = "class Foo:\n    def bar(self):\n        pass"
        execute(code, {}, ns, frame_number=1)
        src = inspect.getsource(ns["Foo"])
        assert "class Foo:" in src

    def test_source_precise_multiple_functions(self):
        """Each function's inspect.getsource returns its own definition span."""
        ns = bare_ns()
        code = "def foo():\n    return 1\n\ndef bar():\n    return 2"
        execute(code, {}, ns, frame_number=1)
        foo_src = inspect.getsource(ns["foo"])
        bar_src = inspect.getsource(ns["bar"])
        assert "def foo" in foo_src
        assert "def bar" not in foo_src
        assert "def bar" in bar_src
        assert "def foo" not in bar_src

    def test_source_redefine(self):
        """After redefinition under a different frame number, inspect.getsource
        on the new function returns the new source."""
        ns = bare_ns()
        execute("def greet():\n    return 'old'", {}, ns, frame_number=1)
        execute("def greet():\n    return 'new'", {}, ns, frame_number=2)
        src = inspect.getsource(ns["greet"])
        assert "new" in src

    def test_function_callable_after_execute(self):
        ns = bare_ns()
        execute("def double(x):\n    return x * 2", {}, ns, frame_number=1)
        assert ns["double"](5) == 10

    def test_persistent_across_calls(self):
        """Multiple execute calls share the same ns; variables persist."""
        ns = bare_ns()
        execute("x = 10", {}, ns, frame_number=1)
        execute("y = x + 5", {}, ns, frame_number=2)
        assert ns["y"] == 15

    def test_system_exit_captured_as_error(self):
        """LLM calling sys.exit() should not terminate the process; it should be captured in ExecResult.error."""
        ns = bare_ns()
        result = execute("import sys; sys.exit(0)", {}, ns, frame_number=1)
        assert isinstance(result.error, SystemExit)

    def test_exit_builtin_captured_as_error(self):
        """LLM calling builtin exit() should not terminate the process; it should be captured in ExecResult.error."""
        ns = bare_ns()
        result = execute("exit(0)", {}, ns, frame_number=1)
        assert isinstance(result.error, SystemExit)

    def test_redefine_to_builtin_no_crash(self):
        """When a function is reassigned to a builtin object, execute does not crash."""
        ns = bare_ns()
        result = execute("def foo():\n    pass\nfoo = 42", {}, ns, frame_number=1)
        assert result.error is None
        assert ns["foo"] == 42

    def test_frame_not_written_by_execute(self):
        """execute() does not write ns['_frame']; that is _commit's responsibility."""
        ns = bare_ns()
        initial = ns.get("_frame", 0)
        execute("x = 1", {}, ns, frame_number=5)
        assert ns.get("_frame", 0) == initial


# ─────────────────────────────────────────────
# Kernel render integration (v3)
# ─────────────────────────────────────────────

class TestRenderIntegration:
    """Kernel.render/ping integration tests with the v3 renderer."""

    def test_render_returns_str(self):
        from vessal.ark.shell.hull.cell.protocol import Ping
        k = minimal_kernel()
        result = k.ping(None, _ns(k))
        assert isinstance(result, Ping)
        # After ping(None, ...) signals are always scanned; verify non-empty
        result2 = k.ping(None, _ns(k))
        assert isinstance(result2, Ping)
        assert len(result2.state.signals) > 0

    def test_exec_operation_result_affects_render(self):
        """render reflects state changes after exec via ping."""
        from vessal.ark.shell.hull.cell.protocol import Ping
        k = minimal_kernel()
        state = _exec(k, "print('hi')\nx = 1")
        assert isinstance(state, Ping)

    def test_stdout_in_ns_after_exec_operation(self):
        """observation.stdout is populated after exec via ping."""
        k = minimal_kernel()
        _exec(k, "print('hello from kernel')")
        assert "hello from kernel" in k.L["observation"].stdout

    def test_frame_stream_in_state(self):
        """State.frame_stream is a FrameStream dataclass (not a rendered string)."""
        from vessal.ark.shell.hull.cell.protocol import FRAME_SCHEMA_VERSION, FrameStream as ProtocolFrameStream
        k = minimal_kernel()
        ping = k.ping(None, _ns(k))
        assert isinstance(ping.state.frame_stream, ProtocolFrameStream)

    def test_context_budget_removed_from_l(self):
        """PR 5: _context_budget / _context_pct are no longer seeded in L."""
        k = minimal_kernel()
        assert "_context_budget" not in k.L
        assert "_context_pct" not in k.L

    def test_auxiliary_section_in_output(self):
        """Signals dict contains system signal key with 'context' payload key."""
        k = minimal_kernel()
        pong = k.ping(None, _ns(k))
        assert isinstance(pong.state.signals, dict)
        assert any(
            isinstance(payload, dict) and "context" in payload
            for payload in pong.state.signals.values()
        )


# ─────────────────────────────────────────────
# Kernel integration tests
# ─────────────────────────────────────────────

class TestKernel:
    def test_init_creates_system_vars(self):
        """After init, ns contains all required system variables (v5 format)."""
        k = minimal_kernel()
        assert k.L.get("_frame") == 0
        # _system_prompt lives in G (written by boot script, never in L)
        assert "_system_prompt" not in k.L
        # _frame_stream removed from L in PR 5 (reads from SQLite each ping)
        assert "_frame_stream" not in k.L
        # _history and _history_depth removed in v3
        assert "_history" not in k.L
        assert "_history_depth" not in k.L

    def test_init_creates_lifecycle_vars(self):
        """After init, ns contains _sleeping/_next_wake lifecycle variables."""
        k = minimal_kernel()
        assert k.L["_sleeping"] is False
        assert k.L["_next_wake"] is None
        # _wake moved to G["_system"].set_wake() in PR 3
        assert "_wake" not in k.L

    def test_init_from_snapshot(self):
        """snapshot_path parameter: restore namespace from file to continue a previous session."""
        k = minimal_kernel()
        _exec(k, "counter = 10")

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            snap_path = f.name

        try:
            k.snapshot(snap_path)
            # Init new Kernel with snapshot_path; restores state directly
            k2 = minimal_kernel(restore_path=snap_path)
            assert k2.L["counter"] == 10
        finally:
            os.unlink(snap_path)

    def test_ns_is_exposed(self):
        """kernel.L is fully exposed and directly readable/writable."""
        k = minimal_kernel()
        assert isinstance(k.L, dict)
        # can write directly
        k.L["custom_var"] = "hello"
        assert k.L["custom_var"] == "hello"

    def test_exec_via_ping_returns_ping(self):
        """ping(pong, ns) returns Ping after executing code."""
        from vessal.ark.shell.hull.cell.protocol import Ping
        k = minimal_kernel()
        result = _exec(k, "x = 1")
        assert isinstance(result, Ping)

    def test_ping_none_returns_ping(self):
        """ping(None, ns) returns Ping (boot call)."""
        from vessal.ark.shell.hull.cell.protocol import Ping
        k = minimal_kernel()
        result = k.ping(None, _ns(k))
        assert isinstance(result, Ping)

    def test_ping_none_does_not_increment_frame(self):
        """ping(None, ns) does not increment the frame number."""
        k = minimal_kernel()
        frame_before = k.L["_frame"]
        k.ping(None, _ns(k))
        assert k.L["_frame"] == frame_before

    def test_ping_none_does_not_append_frame_stream(self):
        """ping(None, ns) does not commit a frame (no exec/eval/write)."""
        k = minimal_kernel()
        frame_before = k.L["_frame"]
        k.ping(None, _ns(k))
        k.ping(None, _ns(k))
        # _frame_stream removed from L in PR 5; _frame counter must not advance
        assert "_frame_stream" not in k.L
        assert k.L["_frame"] == frame_before

    def test_kernel_ping_returns_ping(self, tmp_path):
        from vessal.ark.shell.hull.cell.protocol import Ping
        kernel = minimal_kernel()
        kernel.G["_system_prompt"] = "You are an agent."
        ping = kernel.ping(None, _ns(kernel))
        assert isinstance(ping, Ping)
        assert ping.system_prompt == "You are an agent."

    def test_exec_via_ping_does_not_set_frame_before_pong(self):
        """ping(pong, ns) increments _frame exactly once (via _commit)."""
        k = minimal_kernel()
        initial = k.L["_frame"]
        _exec(k, "pass")
        assert k.L["_frame"] == initial + 1

    def test_exec_via_ping_increments_frame_counter(self):
        """ping(pong, ns) increments _frame for each committed frame."""
        k = minimal_kernel()
        start = k.L["_frame"]
        _exec(k, "x = 1")
        _exec(k, "y = 2")
        assert k.L["_frame"] == start + 2

    def test_variable_persists_across_pings(self):
        k = minimal_kernel()
        _exec(k, "x = 42")
        _exec(k, "y = x + 1")
        assert k.L["y"] == 43

    def test_stdout_in_observation_after_exec(self):
        """observation.stdout is populated after execution via ping."""
        k = minimal_kernel()
        _exec(k, "print('hello from kernel')")
        assert "hello from kernel" in k.L["observation"].stdout

    def test_error_in_observation_after_exec(self):
        """observation.error is the raw exception when execution raises."""
        k = minimal_kernel()
        _exec(k, "1 / 0")
        assert isinstance(k.L["observation"].error, ZeroDivisionError)

    def test_diff_in_observation_after_exec(self):
        """New variables appear in observation.diff."""
        k = minimal_kernel()
        _exec(k, "alpha = 999")
        assert "alpha" in k.L["observation"].diff

    def test_snapshot_restore(self):
        k = minimal_kernel()
        _exec(k, "counter = 10")

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            snap_path = f.name

        try:
            k.snapshot(snap_path)
            _exec(k, "counter = 999")  # modify state

            k.restore(snap_path)
            # counter should be 10 after restore
            _exec(k, "result = counter")
            assert "counter" in k.L
            assert k.L["counter"] == 10
        finally:
            os.unlink(snap_path)

    def test_snapshot_restore_no_skills(self, tmp_path):
        """snapshot/restore works normally without Skills present in the namespace."""
        k = minimal_kernel()
        _exec(k, "x = 42")
        snap = str(tmp_path / "test.pkl")
        k.snapshot(snap)

        k2 = minimal_kernel()
        k2.restore(snap)
        assert k2.L["x"] == 42
        assert k2.L.get("_loaded_skills", {}) == {}

    def test_snapshot_restore_preserves_builtin_names(self, tmp_path):
        """snapshot/restore preserves _builtin_names list."""
        k = _kw()
        snap = str(tmp_path / "test.pkl")
        k.snapshot(snap)

        k2 = minimal_kernel()
        k2.restore(snap)
        assert isinstance(k2.L["_builtin_names"], list)

    def test_snapshot_is_single_blob_of_ns_dict(self, tmp_path):
        """The snapshot file is a single cloudpickle blob containing the ns dict."""
        import cloudpickle as _cp
        import io
        k = _kw()
        snap = str(tmp_path / "test.pkl")
        k.snapshot(snap)

        raw = Path(snap).read_bytes()
        buf = io.BytesIO(raw)
        ns = _cp.load(buf)
        # Exactly one blob: reading it consumes all bytes
        assert buf.tell() == len(raw)
        assert isinstance(ns, dict)

    def test_snapshot_restore_with_skill(self, tmp_path):
        """After loading a Skill and doing snapshot/restore, the Skill class object is correctly restored."""
        from vessal.skills._base import BaseSkill
        skills_root = str(Path(__file__).resolve().parents[3] / "src" / "vessal" / "skills")
        with patch.dict(sys.modules):
            k = minimal_kernel()
            sm = SkillLoader(skill_paths=[skills_root])
            k.L["_builtin_names"] = []

            skill_cls = sm.load("tasks")
            k.L["tasks_cls"] = skill_cls

            assert issubclass(skill_cls, BaseSkill)

            snap = str(tmp_path / "test.pkl")
            k.snapshot(snap)

            k2 = minimal_kernel()
            k2.restore(snap)

            assert issubclass(k2.L["tasks_cls"], BaseSkill)

    def test_snapshot_restore_skill_with_data(self, tmp_path):
        """Skill-produced data and instances are correctly restored together."""
        from vessal.skills._base import BaseSkill
        skills_root = str(Path(__file__).resolve().parents[3] / "src" / "vessal" / "skills")
        with patch.dict(sys.modules):
            k = minimal_kernel()
            sm = SkillLoader(skill_paths=[skills_root])
            k.L["_builtin_names"] = []

            TasksCls = sm.load("tasks")
            k.L["TasksCls"] = TasksCls
            _exec(k, 't = TasksCls(); task_id = t.add("test goal")')

            assert k.L["task_id"] == "1"

            snap = str(tmp_path / "test.pkl")
            k.snapshot(snap)

            k2 = minimal_kernel()
            k2.restore(snap)

            assert k2.L["task_id"] == "1"
            assert issubclass(k2.L["TasksCls"], BaseSkill)

    def test_restore_cleans_sys_modules(self, tmp_path):
        """restore clears sys.modules cache; does not use stale in-process modules."""
        from vessal.skills._base import BaseSkill
        skills_root = str(Path(__file__).resolve().parents[3] / "src" / "vessal" / "skills")
        with patch.dict(sys.modules):
            k = minimal_kernel()
            sm = SkillLoader(skill_paths=[skills_root])
            k.L["_builtin_names"] = []

            TasksCls = sm.load("tasks")
            k.L["TasksCls"] = TasksCls

            snap = str(tmp_path / "test.pkl")
            k.snapshot(snap)

            k2 = minimal_kernel()
            k2.restore(snap)

            # Skill class should be usable after restore
            assert issubclass(k2.L["TasksCls"], BaseSkill)

    def test_ns_direct_write_affects_exec(self):
        """Writing directly to kernel.L is visible to subsequent ping() calls."""
        k = minimal_kernel()
        k.L["injected"] = 42
        _exec(k, "answer = injected + 1")
        assert k.L["answer"] == 43

    def test_sleeping_lifecycle_var(self):
        """_sleeping is a lifecycle variable in namespace; Agent can set it via sleep()."""
        k = minimal_kernel()
        assert k.L["_sleeping"] is False
        _exec(k, "sleep()")
        assert k.L["_sleeping"] is True

    def test_wake_driven_exec(self):
        """Simulate event-driven execution: write _wake, execute, then call sleep()."""
        k = minimal_kernel()
        k.L["_wake"] = "user_message: compute 1+2+3"
        _exec(k, "total = 1 + 2 + 3")
        _exec(k, "sleep()")
        assert k.L["total"] == 6
        assert k.L["_sleeping"] is True

    def test_eval_expect_returns_verdict(self):
        """ping with expect returns Verdict in L['verdict']."""
        from vessal.ark.shell.hull.cell.protocol import Verdict
        k = minimal_kernel()
        _exec(k, "x = 1")
        _exec(k, "pass", expect="assert x == 1")
        assert isinstance(k.L["verdict"], Verdict)

    def test_eval_expect_passes(self):
        """ping with passing expect: verdict.passed == verdict.total."""
        k = minimal_kernel()
        _exec(k, "x = 42")
        _exec(k, "pass", expect="assert x == 42")
        verdict = k.L["verdict"]
        assert verdict.total == 1
        assert verdict.passed == 1
        assert verdict.failures == ()

    def test_eval_expect_fails(self):
        """ping with failing expect: verdict.failures is non-empty."""
        k = minimal_kernel()
        _exec(k, "x = 1")
        _exec(k, "pass", expect="assert x == 99")
        verdict = k.L["verdict"]
        assert verdict.total == 1
        assert verdict.passed == 0
        assert len(verdict.failures) == 1

    def test_eval_expect_does_not_leak_arbitrary_keys(self):
        """ping with expect evaluates on a copy; post-ping key delta is exactly the allowed set."""
        k = minimal_kernel()
        _exec(k, "x = 1")
        ns_keys_before = set(k.L.keys())
        _exec(k, "pass", expect="assert x == 1")
        allowed_new_keys = {"verdict", "observation", "_frame", "signals",
                            "_context_pct", "_budget_total", "_dropped_frame_count"}
        leaked_extra_keys = set(k.L.keys()) - ns_keys_before - allowed_new_keys
        assert leaked_extra_keys == set(), f"Unexpected new keys after expect: {leaked_extra_keys}"
        assert k.L["x"] == 1

    def test_ping_commits_frame_and_increments(self):
        """ping(pong, ns) commits one frame; _frame increments by 1."""
        from vessal.ark.shell.hull.cell.protocol import Action, Pong

        k = minimal_kernel()
        frame_before = k.L["_frame"]

        _exec(k, "x = 1")

        assert k.L["_frame"] == frame_before + 1


# ─────────────────────────────────────────────
# Bare expression value capture
# ─────────────────────────────────────────────

class TestExprCapture:
    """Bare expression value capture tests."""

    def test_bare_variable(self):
        """Value of a bare variable name is appended to stdout in ExecResult."""
        ns = bare_ns()
        ns["x"] = 42
        result = execute("x", {}, ns, frame_number=1)
        assert "42" in result.stdout

    def test_bare_expression_result(self):
        """Value of a bare expression (e.g. 1+2) is appended to ExecResult.stdout."""
        ns = bare_ns()
        result = execute("1 + 2", {}, ns, frame_number=1)
        assert "3" in result.stdout

    def test_assignment_no_capture(self):
        """Assignment statements do not trigger expression capture."""
        ns = bare_ns()
        result = execute("x = 42", {}, ns, frame_number=1)
        assert result.stdout == ""

    def test_function_def_no_capture(self):
        """Function definitions do not trigger expression capture."""
        ns = bare_ns()
        result = execute("def foo(): pass", {}, ns, frame_number=1)
        assert result.stdout == ""

    def test_print_plus_expr(self):
        """Both print output and bare expression value appear in ExecResult.stdout."""
        ns = bare_ns()
        result = execute("print('out')\n1 + 1", {}, ns, frame_number=1)
        assert "out" in result.stdout
        assert "2" in result.stdout

    def test_none_result_not_shown(self):
        """Expression value of None is not appended to ExecResult.stdout."""
        ns = bare_ns()
        result = execute("None", {}, ns, frame_number=1)
        assert result.stdout == ""

    def test_long_repr_truncated(self):
        """Oversized repr is truncated to _EXPR_REPR_MAX_LEN characters."""
        ns = bare_ns()
        ns["big"] = list(range(100000))
        result = execute("big", {}, ns, frame_number=1)
        assert len(result.stdout) <= 2010  # repr + "\n"

    def test_syntax_error_passthrough(self):
        """Syntax errors are executed as-is; the error is captured in ExecResult.error; no crash."""
        ns = bare_ns()
        result = execute("def foo(:\n    pass", {}, ns, frame_number=1)
        assert result.error is not None

    def test_source_uses_original_action(self):
        """source_cache registers the original operation text (NOT the
        bare-expression-rewritten modified_operation). For pure-def code
        the two are identical, but the registration target is operation;
        verify via inspect.getsource."""
        ns = bare_ns()
        code = "def add(a, b):\n    return a + b"
        execute(code, {}, ns, frame_number=1)
        src = inspect.getsource(ns["add"])
        assert "def add(a, b):" in src
        assert "return a + b" in src

    def test_expr_result_not_in_namespace(self):
        """_expr_result does not persist in namespace."""
        ns = bare_ns()
        execute("42", {}, ns, frame_number=1)
        assert "_expr_result" not in ns

    def test_expr_result_not_in_diff(self):
        """_expr_result does not appear in ExecResult.diff (system variable with _ prefix)."""
        ns = bare_ns()
        result = execute("42", {}, ns, frame_number=1)
        assert "_expr_result" not in result.diff

    def test_maybe_capture_assignment_unchanged(self):
        """_maybe_capture_last_expr does not rewrite assignment statements."""
        assert _maybe_capture_last_expr("x = 42") == "x = 42"

    def test_maybe_capture_expr_rewritten(self):
        """_maybe_capture_last_expr rewrites bare expressions as assignments."""
        result = _maybe_capture_last_expr("42")
        assert "_expr_result" in result
        assert "42" in result

    def test_maybe_capture_syntax_error_passthrough(self):
        """Returns original string on syntax error."""
        bad = "def foo(:"
        assert _maybe_capture_last_expr(bad) == bad

    def test_print_returns_none_no_extra_stdout(self):
        """print() is a bare expression but returns None; no extra output is produced."""
        ns = bare_ns()
        result = execute("print('hi')", {}, ns, frame_number=1)
        assert result.stdout == "hi\n"


# ─────────────────────────────────────────────
# kernel.step() return value
# ─────────────────────────────────────────────

class TestPingReturnsPing:
    """kernel.ping() returns a Ping, never None."""

    def test_ping_returns_ping(self):
        """ping() returns a Ping object."""
        from vessal.ark.shell.hull.cell.kernel import Kernel
        from vessal.ark.shell.hull.cell.protocol import Action, Ping, Pong

        k = minimal_kernel()
        k.G["_system_prompt"] = "test"
        pong = Pong(think="t", action=Action(operation="x = 1", expect=""))
        result = k.ping(pong, _ns(k))
        assert isinstance(result, Ping), f"Expected Ping, got {type(result)}"





# ─────────────────────────────────────────────
# inspect.getsource — linecache-backed source recovery (PR 2 contract)
# ─────────────────────────────────────────────

class TestInspectGetSource:
    """Lock in the contract that PR 2 (cf5836f) established: stdlib
    inspect.getsource works on Kernel-defined functions and classes,
    both immediately after exec and after a snapshot/restore round trip
    backed by a SQLite frame_log.

    These tests deliberately avoid asserting anything about a `_source`
    attribute — that mechanism was retired in this PR. The contract is
    purely on inspect.getsource against linecache.
    """

    def test_inspect_getsource_function_after_execute(self):
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = minimal_kernel()
        _exec(k, "def add(a, b):\n    return a + b")
        src = inspect.getsource(k.L["add"])
        assert "def add(a, b):" in src
        assert "return a + b" in src

    def test_inspect_getsource_class_after_execute(self):
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = minimal_kernel()
        _exec(k, "class Bar:\n    def m(self):\n        return 1")
        src = inspect.getsource(k.L["Bar"])
        assert "class Bar:" in src
        assert "def m(self):" in src

    def test_inspect_getsource_async_function(self):
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = minimal_kernel()
        _exec(k, "async def waiter():\n    return 42")
        src = inspect.getsource(k.L["waiter"])
        assert "async def waiter" in src

    def test_inspect_getsource_decorated_function_includes_decorator(self):
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = minimal_kernel()
        code = (
            "def my_decorator(fn):\n"
            "    return fn\n"
            "\n"
            "@my_decorator\n"
            "def decorated():\n"
            "    return 42"
        )
        _exec(k, code)
        src = inspect.getsource(k.L["decorated"])
        assert "@my_decorator" in src
        assert "def decorated" in src

    def test_inspect_getsource_distinct_per_function(self):
        """Two functions defined in the same operation each map to the
        single shared <frame-N> source; inspect.getsource returns the
        function's own definition span via the function's lineno."""
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = minimal_kernel()
        code = "def foo():\n    return 1\n\ndef bar():\n    return 2"
        _exec(k, code)
        foo_src = inspect.getsource(k.L["foo"])
        bar_src = inspect.getsource(k.L["bar"])
        assert "def foo" in foo_src
        assert "def bar" not in foo_src
        assert "def bar" in bar_src
        assert "def foo" not in bar_src
