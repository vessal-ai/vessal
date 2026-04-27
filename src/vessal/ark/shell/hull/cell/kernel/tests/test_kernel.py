# tests/test_kernel.py — Kernel unit tests (v3 renderer)
#
# Test coverage:
#   TestIsUserVar       is_user_var helper function
#   TestExecute         execute() — execute code, side effects written to ns
#   TestCompressTraceback  _compress_traceback() — long traceback compression
#   TestKernel          Kernel class integration tests (including ns exposure, render method)
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vessal.ark.shell.hull.cell.kernel import Kernel
from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream

from vessal.ark.shell.hull.cell.kernel.executor import ExecResult, is_user_var, execute, _compress_traceback, _maybe_capture_last_expr
from vessal.ark.shell.hull.cell.kernel.render import render
from vessal.ark.shell.hull.skill_loader import SkillLoader


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
        "_system_prompt": "",
        "_pins": set(),
        "_log_path": "",
        "_context_pct": 0,
        "_ns_meta": {},
        "_frame_stream": FrameStream(k=16, n=8),
        "_progress": "",
    }


def _kw() -> "Kernel":
    """Create Kernel with minimal namespace setup (test helper)."""
    k = Kernel()
    k.ns["_builtin_names"] = []
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
    def test_empty_action_resets_side_effects(self):
        """Empty operation resets the four side-effect variables to empty values; no code is executed."""
        ns = bare_ns()
        # execute once to leave side effects
        execute("x = 1", ns, frame_number=1)
        # execute empty code
        execute("", ns, frame_number=2)
        assert ns["_operation"] == ""
        assert ns["_stdout"] == ""
        assert ns["_error"] is None
        assert ns["_diff"] == ""

    def test_whitespace_action_treated_as_empty(self):
        ns = bare_ns()
        execute("   \n  ", ns, frame_number=1)
        assert ns["_operation"] == ""

    def test_none_action_treated_as_empty(self):
        ns = bare_ns()
        execute(None, ns, frame_number=1)
        assert ns["_operation"] == ""

    def test_returns_exec_result(self):
        """execute returns an ExecResult."""
        ns = bare_ns()
        result = execute("x = 1", ns, frame_number=1)
        assert isinstance(result, ExecResult)

    def test_operation_recorded(self):
        ns = bare_ns()
        code = "x = 42"
        execute(code, ns, frame_number=1)
        assert ns["_operation"] == code

    def test_simple_assignment(self):
        ns = bare_ns()
        execute("x = 42", ns, frame_number=1)
        assert ns["x"] == 42
        assert ns["_error"] is None

    def test_stdout_captured(self):
        ns = bare_ns()
        execute("print('hello world')", ns, frame_number=1)
        assert ns["_stdout"] == "hello world\n"
        assert ns["_error"] is None

    def test_multiple_prints(self):
        ns = bare_ns()
        execute("print('a')\nprint('b')", ns, frame_number=1)
        assert "a\n" in ns["_stdout"]
        assert "b\n" in ns["_stdout"]

    def test_stdout_empty_when_no_print(self):
        ns = bare_ns()
        execute("x = 1", ns, frame_number=1)
        assert ns["_stdout"] == ""

    def test_runtime_error_captured(self):
        ns = bare_ns()
        execute("1 / 0", ns, frame_number=1)
        assert ns["_error"] is not None
        assert "ZeroDivisionError" in ns["_error"]

    def test_syntax_error_captured(self):
        ns = bare_ns()
        execute("def foo(:\n    pass", ns, frame_number=1)
        assert ns["_error"] is not None

    def test_name_error_captured(self):
        ns = bare_ns()
        execute("y = undefined_var", ns, frame_number=1)
        assert ns["_error"] is not None
        assert "NameError" in ns["_error"]

    def test_error_none_on_success(self):
        ns = bare_ns()
        execute("x = 1", ns, frame_number=1)
        assert ns["_error"] is None

    def test_no_builtins_pollution(self):
        """__builtins__ injected by exec should be cleaned up."""
        ns = bare_ns()
        execute("x = 1", ns, frame_number=1)
        assert "__builtins__" not in ns

    def test_diff_added(self):
        ns = bare_ns()
        execute("a = 1\nb = 'hello'", ns, frame_number=1)
        assert "+a = 1" in ns["_diff"]
        assert "+b = hello" in ns["_diff"]

    def test_diff_modified(self):
        ns = bare_ns()
        execute("x = 1", ns, frame_number=1)
        execute("x = 99", ns, frame_number=2)
        assert "-x = 1" in ns["_diff"]
        assert "+x = 99" in ns["_diff"]

    def test_diff_deleted(self):
        ns = bare_ns()
        execute("x = 1", ns, frame_number=1)
        execute("del x", ns, frame_number=2)
        assert "-x = 1" in ns["_diff"]

    def test_diff_ignores_system_vars(self):
        """Variables starting with _ do not participate in diff."""
        ns = bare_ns()
        execute("_observe = ['x']", ns, frame_number=1)
        assert ns["_diff"] == ""

    def test_diff_empty_when_no_change(self):
        ns = bare_ns()
        execute("pass", ns, frame_number=1)
        assert ns["_diff"] == ""

    def test_history_not_managed_by_execute(self):
        """executor does not commit to _frame_stream; frame logging is managed by Cell (Phase 3)."""
        ns = bare_ns()
        execute("x = 1", ns, frame_number=1)
        execute("y = 2", ns, frame_number=2)
        # execute should not commit to _frame_stream
        assert ns["_frame_stream"].hot_frame_count() == 0

    def test_source_function_on_object(self):
        """Function source is recoverable via inspect.getsource (linecache)."""
        import inspect
        ns = bare_ns()
        code = "def add(a, b):\n    return a + b"
        execute(code, ns, frame_number=1)
        src = inspect.getsource(ns["add"])
        assert "def add(a, b):" in src
        assert "return a + b" in src

    def test_source_class_on_object(self):
        import inspect
        ns = bare_ns()
        code = "class Foo:\n    def bar(self):\n        pass"
        execute(code, ns, frame_number=1)
        src = inspect.getsource(ns["Foo"])
        assert "class Foo:" in src

    def test_source_precise_multiple_functions(self):
        """Each function's inspect.getsource returns its own definition span."""
        import inspect
        ns = bare_ns()
        code = "def foo():\n    return 1\n\ndef bar():\n    return 2"
        execute(code, ns, frame_number=1)
        foo_src = inspect.getsource(ns["foo"])
        bar_src = inspect.getsource(ns["bar"])
        assert "def foo" in foo_src
        assert "def bar" not in foo_src
        assert "def bar" in bar_src
        assert "def foo" not in bar_src

    def test_source_redefine(self):
        """After redefinition under a different frame number, inspect.getsource
        on the new function returns the new source."""
        import inspect
        ns = bare_ns()
        execute("def greet():\n    return 'old'", ns, frame_number=1)
        execute("def greet():\n    return 'new'", ns, frame_number=2)
        src = inspect.getsource(ns["greet"])
        assert "new" in src

    def test_function_callable_after_execute(self):
        ns = bare_ns()
        execute("def double(x):\n    return x * 2", ns, frame_number=1)
        assert ns["double"](5) == 10

    def test_persistent_across_calls(self):
        """Multiple execute calls share the same ns; variables persist."""
        ns = bare_ns()
        execute("x = 10", ns, frame_number=1)
        execute("y = x + 5", ns, frame_number=2)
        assert ns["y"] == 15

    def test_system_exit_captured_as_error(self):
        """LLM calling sys.exit() should not terminate the process; it should be captured as _error."""
        ns = bare_ns()
        execute("import sys; sys.exit(0)", ns, frame_number=1)
        assert ns["_error"] is not None
        assert "SystemExit" in ns["_error"]

    def test_exit_builtin_captured_as_error(self):
        """LLM calling builtin exit() should not terminate the process; it should be captured as _error."""
        ns = bare_ns()
        execute("exit(0)", ns, frame_number=1)
        assert ns["_error"] is not None
        assert "SystemExit" in ns["_error"]

    def test_redefine_to_builtin_no_crash(self):
        """When a function is reassigned to a builtin object, execute does not crash."""
        ns = bare_ns()
        execute("def foo():\n    pass\nfoo = 42", ns, frame_number=1)
        assert ns["_error"] is None
        assert ns["foo"] == 42

    def test_frame_not_written_by_execute(self):
        """execute() does not write ns['_frame']; that is _commit_frame's responsibility."""
        ns = bare_ns()
        initial = ns.get("_frame", 0)
        execute("x = 1", ns, frame_number=5)
        assert ns.get("_frame", 0) == initial


# ─────────────────────────────────────────────
# _compress_traceback
# ─────────────────────────────────────────────

class TestCompressTraceback:
    """_compress_traceback internal function: compresses long tracebacks."""

    def _make_tb(self, n_lib_frames: int, has_user_frame: bool = True) -> str:
        """Construct a traceback with n_lib_frames library frames + optional user frame + exception line."""
        lines = ["Traceback (most recent call last):"]
        for i in range(n_lib_frames):
            lines.append(f'  File "/lib/mod_{i}.py", line {i + 1}, in func_{i}')
            lines.append(f"    call_{i}()")
        if has_user_frame:
            lines.append('  File "<frame-1>", line 5, in <module>')
            lines.append("    result = bad_function()")
        lines.append("ValueError: something went wrong")
        return "\n".join(lines)

    def test_short_traceback_unchanged(self):
        """Returned unchanged when <= 20 lines; no compression."""
        tb = self._make_tb(3)  # 1 + 6 + 2 + 1 = 10 lines
        assert _compress_traceback(tb) == tb

    def test_long_traceback_compressed(self):
        """> 20 lines: compressed; first line, user frame, and exception line are retained."""
        tb = self._make_tb(15)  # 1 + 30 + 2 + 1 = 34 lines
        result = _compress_traceback(tb)
        assert len(result) < len(tb)
        assert result.startswith("Traceback (most recent call last):")
        assert "lines omitted" in result
        assert 'File "<frame-1>"' in result
        assert "ValueError: something went wrong" in result

    def test_omitted_count_accurate(self):
        """Omitted line count equals (total lines - first line - user frame lines - exception line)."""
        tb = self._make_tb(15)  # total 34 lines: first 1 + lib frames 30 + user frame 2 + exception 1
        result = _compress_traceback(tb)
        # Retained: first line + user frame 2 lines + exception 1 line = 4 (plus omission notice)
        # Omitted: 34 - 1 - 2 - 1 = 30
        assert "30 lines omitted" in result

    def test_no_user_frame_still_shows_exception(self):
        """Without a File \"<string>\" frame, compression still works and retains the exception line."""
        tb = self._make_tb(15, has_user_frame=False)  # pure library frames
        result = _compress_traceback(tb)
        assert "ValueError: something went wrong" in result
        assert "lines omitted" in result

    def test_execute_compresses_deep_traceback(self):
        """execute() compresses exceptions from deep call stacks."""
        ns = bare_ns()
        # Python 3.12 exec traceback has 1 line per frame (no code line); need > _TRACEBACK_COMPRESS_THRESHOLD
        # frames to trigger compression. range(20) produces f0-f19, plus f20 (raises) = 21 function frames
        # + 2 module frames + first line + exception = 25 lines.
        funcs = "\n".join(
            f"def f{i}(): return f{i+1}()" for i in range(20)
        )
        code = f"{funcs}\ndef f20(): return 1/0\nf0()"
        execute(code, ns, frame_number=1)
        error = ns["_error"]
        assert error is not None
        assert "ZeroDivisionError" in error
        # After compression there should be an omission notice (call chain is deep enough, > 20 lines)
        assert "lines omitted" in error

    def test_execute_short_error_not_compressed(self):
        """Simple exceptions in execute() are not compressed; full traceback is retained."""
        ns = bare_ns()
        execute("1 / 0", ns, frame_number=1)
        error = ns["_error"]
        assert error is not None
        # Short traceback does not contain omission notice
        assert "lines omitted" not in error


# ─────────────────────────────────────────────
# Kernel render integration (v3)
# ─────────────────────────────────────────────

class TestRenderIntegration:
    """Kernel.render() integration tests with the v3 renderer."""

    def test_render_returns_str(self):
        from vessal.ark.shell.hull.cell.protocol import Ping
        k = Kernel()
        result = k.render()
        assert isinstance(result, Ping)
        # New mechanism: render only reads _signal_outputs; signals being empty before
        # update_signals() is called is normal. Verify that update_signals() + render()
        # together return non-empty content.
        k.update_signals()
        result2 = k.render()
        assert isinstance(result2, Ping)
        assert len(result2.state.signals) > 0

    def test_exec_operation_result_affects_render(self):
        """render reflects state changes after exec_operation."""
        from vessal.ark.shell.hull.cell.protocol import Ping
        k = Kernel()
        frame = k.ns.get("_frame", 0) + 1
        k.exec_operation("print('hi')\nx = 1", frame_number=frame)
        state = k.render()
        assert isinstance(state, Ping)

    def test_stdout_in_ns_after_exec_operation(self):
        """_stdout is written to ns after exec_operation; readable."""
        k = Kernel()
        k.exec_operation("print('hello from kernel')", frame_number=1)
        assert "hello from kernel" in k.ns["_stdout"]

    def test_frame_stream_in_state(self):
        """Frame stream section appears in the rendered output."""
        from vessal.ark.shell.hull.cell.protocol import FRAME_SCHEMA_VERSION
        k = Kernel()
        # Manually commit a frame dict into _frame_stream to trigger the frame stream section
        k.ns["_frame_stream"].commit_frame({
            "schema_version": FRAME_SCHEMA_VERSION,
            "number": 1,
            "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
            "pong": {"think": "", "action": {"operation": "x = 1", "expect": ""}},
            "observation": {"stdout": "", "diff": "+x = 1", "error": None, "verdict": None},
        })
        ping = k.render()
        assert "══════ frame stream ══════" in ping.state.frame_stream

    def test_context_budget_default_set_by_kernel(self):
        """Kernel init sets the default _context_budget in ns."""
        k = Kernel()
        assert "_context_budget" in k.ns
        assert k.ns["_context_budget"] == 128000

    def test_auxiliary_section_in_output(self):
        """Auxiliary section (system variables) appears in render output after update_signals()."""
        k = Kernel()
        k.update_signals()
        pong = k.render()
        assert "context" in pong.state.signals


# ─────────────────────────────────────────────
# Kernel integration tests
# ─────────────────────────────────────────────

class TestKernel:
    def test_init_creates_system_vars(self):
        """After init, ns contains all required system variables (v4 format)."""
        k = Kernel()
        assert k.ns.get("_frame") == 0
        # v4 vars
        assert k.ns.get("_system_prompt") == ""
        assert isinstance(k.ns.get("_frame_stream"), FrameStream)
        # _history and _history_depth removed in v3
        assert "_history" not in k.ns
        assert "_history_depth" not in k.ns

    def test_init_creates_lifecycle_vars(self):
        """After init, ns contains _sleeping/_wake/_next_wake lifecycle variables."""
        k = Kernel()
        assert k.ns["_sleeping"] is False
        assert k.ns["_wake"] == ""
        assert k.ns["_next_wake"] is None

    def test_init_from_snapshot(self):
        """snapshot_path parameter: restore namespace from file to continue a previous session."""
        k = Kernel()
        k.exec_operation("counter = 10", frame_number=1)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            snap_path = f.name

        try:
            k.snapshot(snap_path)
            # Init new Kernel with snapshot_path; restores state directly
            k2 = Kernel(snapshot_path=snap_path)
            assert k2.ns["counter"] == 10
        finally:
            os.unlink(snap_path)

    def test_ns_is_exposed(self):
        """kernel.ns is fully exposed and directly readable/writable."""
        k = Kernel()
        assert isinstance(k.ns, dict)
        # can write directly
        k.ns["custom_var"] = "hello"
        assert k.ns["custom_var"] == "hello"

    def test_exec_operation_returns_exec_result(self):
        """exec_operation() returns ExecResult."""
        k = Kernel()
        result = k.exec_operation("x = 1", frame_number=1)
        assert isinstance(result, ExecResult)

    def test_exec_operation_empty_returns_exec_result(self):
        """exec_operation() returns ExecResult for empty code."""
        k = Kernel()
        result = k.exec_operation("", frame_number=1)
        assert isinstance(result, ExecResult)

    def test_render_method_returns_str(self):
        """render() method does not execute code; only renders current state. Has content after update_signals()."""
        from vessal.ark.shell.hull.cell.protocol import Ping
        k = Kernel()
        k.update_signals()
        ping = k.render()
        assert isinstance(ping, Ping)
        assert len(ping.state.signals) > 0

    def test_render_method_does_not_increment_frame(self):
        """render() does not increment the frame number."""
        k = Kernel()
        frame_before = k.ns["_frame"]
        k.render()
        assert k.ns["_frame"] == frame_before

    def test_render_method_does_not_append_frame_stream(self):
        """render() does not commit to the frame stream (_frame_stream)."""
        k = Kernel()
        k.render()
        k.render()
        assert k.ns["_frame_stream"].hot_frame_count() == 0

    def test_kernel_render_returns_ping(self, tmp_path):
        from vessal.ark.shell.hull.cell.protocol import Ping
        kernel = Kernel()
        kernel.ns["_system_prompt"] = "You are an agent."
        ping = kernel.render()
        assert isinstance(ping, Ping)
        assert ping.system_prompt == "You are an agent."

    def test_exec_operation_does_not_set_frame(self):
        """exec_operation does not write ns['_frame']; that is _commit_frame's responsibility."""
        k = Kernel()
        initial = k.ns["_frame"]
        k.exec_operation("pass", frame_number=5)
        assert k.ns["_frame"] == initial

    def test_exec_operation_does_not_append_frame_stream(self):
        """exec_operation does not commit to _frame_stream (Cell's responsibility, Phase 3)."""
        k = Kernel()
        k.exec_operation("x = 1", frame_number=1)
        k.exec_operation("y = 2", frame_number=2)
        assert k.ns["_frame_stream"].hot_frame_count() == 0

    def test_variable_persists_across_exec_operations(self):
        k = Kernel()
        k.exec_operation("x = 42", frame_number=1)
        k.exec_operation("y = x + 1", frame_number=2)
        assert k.ns["y"] == 43

    def test_stdout_in_ns_after_exec(self):
        """_stdout is written to ns after execution."""
        k = Kernel()
        k.exec_operation("print('hello from kernel')", frame_number=1)
        assert "hello from kernel" in k.ns["_stdout"]

    def test_error_in_ns_after_exec(self):
        """Exception is captured into ns['_error']."""
        k = Kernel()
        k.exec_operation("1 / 0", frame_number=1)
        assert k.ns["_error"] is not None
        assert "ZeroDivisionError" in k.ns["_error"]

    def test_diff_in_ns_after_exec(self):
        """New variables appear in diff."""
        k = Kernel()
        k.exec_operation("alpha = 999", frame_number=1)
        assert "alpha" in k.ns["_diff"]

    def test_snapshot_restore(self):
        k = Kernel()
        k.exec_operation("counter = 10", frame_number=1)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            snap_path = f.name

        try:
            k.snapshot(snap_path)
            k.exec_operation("counter = 999", frame_number=2)  # modify state

            k.restore(snap_path)
            # counter should be 10 after restore
            k.exec_operation("result = counter", frame_number=1)
            assert "counter" in k.ns
            assert k.ns["counter"] == 10
        finally:
            os.unlink(snap_path)

    def test_snapshot_restore_no_skills(self, tmp_path):
        """snapshot/restore works normally without Skills present in the namespace."""
        k = Kernel()
        k.exec_operation("x = 42", frame_number=1)
        snap = str(tmp_path / "test.pkl")
        k.snapshot(snap)

        k2 = Kernel()
        k2.restore(snap)
        assert k2.ns["x"] == 42
        assert k2.ns.get("_loaded_skills", {}) == {}

    def test_snapshot_restore_preserves_builtin_names(self, tmp_path):
        """snapshot/restore preserves _builtin_names list."""
        k = _kw()
        snap = str(tmp_path / "test.pkl")
        k.snapshot(snap)

        k2 = Kernel()
        k2.restore(snap)
        assert isinstance(k2.ns["_builtin_names"], list)

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
        from vessal.ark.shell.hull.skill import SkillBase
        skills_root = str(Path(__file__).resolve().parents[8] / "src" / "vessal" / "skills")
        with patch.dict(sys.modules):
            k = Kernel()
            sm = SkillLoader(skill_paths=[skills_root])
            k.ns["_builtin_names"] = []

            skill_cls = sm.load("tasks")
            k.ns["tasks_cls"] = skill_cls

            assert issubclass(skill_cls, SkillBase)

            snap = str(tmp_path / "test.pkl")
            k.snapshot(snap)

            k2 = Kernel()
            k2.restore(snap)

            assert issubclass(k2.ns["tasks_cls"], SkillBase)

    def test_snapshot_restore_skill_with_data(self, tmp_path):
        """Skill-produced data and instances are correctly restored together."""
        from vessal.ark.shell.hull.skill import SkillBase
        skills_root = str(Path(__file__).resolve().parents[8] / "src" / "vessal" / "skills")
        with patch.dict(sys.modules):
            k = Kernel()
            sm = SkillLoader(skill_paths=[skills_root])
            k.ns["_builtin_names"] = []

            TasksCls = sm.load("tasks")
            k.ns["TasksCls"] = TasksCls
            k.exec_operation('t = TasksCls(); task_id = t.add("test goal")', frame_number=1)

            assert k.ns["task_id"] == "1"

            snap = str(tmp_path / "test.pkl")
            k.snapshot(snap)

            k2 = Kernel()
            k2.restore(snap)

            assert k2.ns["task_id"] == "1"
            assert issubclass(k2.ns["TasksCls"], SkillBase)

    def test_snapshot_partial_on_unpicklable(self, tmp_path):
        """When namespace contains unpicklable objects, snapshot does partial save without raising.

        Uses mock to control cloudpickle.dumps behavior: triggers fallback when
        full serialization fails; filters per-key and saves only serializable keys.
        """
        import cloudpickle as cp
        from unittest.mock import patch

        k = Kernel()
        k.ns["good"] = {"data": 42}
        k.ns["bad"] = object()  # placeholder; will be marked unpicklable by mock
        bad_obj = k.ns["bad"]
        original_dumps = cp.dumps

        # Full ns dump fails; individual dump of bad_obj also fails; others succeed.
        def selective_dumps(obj, *args, **kwargs):
            if obj is k.ns:
                raise TypeError("simulate: cannot pickle namespace")
            if obj is bad_obj:
                raise TypeError("simulate: cannot pickle bad_obj")
            return original_dumps(obj, *args, **kwargs)

        snap = str(tmp_path / "partial.pkl")
        with patch("vessal.ark.shell.hull.cell.kernel.kernel.cloudpickle.dumps", selective_dumps):
            k.snapshot(snap)  # should not raise

        k2 = Kernel()
        k2.restore(snap)
        assert k2.ns["good"] == {"data": 42}
        assert "bad" not in k2.ns  # unpicklable key was skipped

    def test_restore_cleans_sys_modules(self, tmp_path):
        """restore clears sys.modules cache; does not use stale in-process modules."""
        from vessal.ark.shell.hull.skill import SkillBase
        skills_root = str(Path(__file__).resolve().parents[8] / "src" / "vessal" / "skills")
        with patch.dict(sys.modules):
            k = Kernel()
            sm = SkillLoader(skill_paths=[skills_root])
            k.ns["_builtin_names"] = []

            TasksCls = sm.load("tasks")
            k.ns["TasksCls"] = TasksCls

            snap = str(tmp_path / "test.pkl")
            k.snapshot(snap)

            k2 = Kernel()
            k2.restore(snap)

            # Skill class should be usable after restore
            assert issubclass(k2.ns["TasksCls"], SkillBase)

    def test_ns_direct_write_affects_exec(self):
        """Writing directly to kernel.ns is visible to subsequent exec_operation() calls."""
        k = Kernel()
        k.ns["injected"] = 42
        k.exec_operation("answer = injected + 1", frame_number=1)
        assert k.ns["answer"] == 43

    def test_sleeping_lifecycle_var(self):
        """_sleeping is a lifecycle variable in namespace; Agent can set it via sleep()."""
        k = Kernel()
        assert k.ns["_sleeping"] is False
        k.exec_operation("sleep()", frame_number=1)
        assert k.ns["_sleeping"] is True

    def test_wake_driven_exec(self):
        """Simulate event-driven execution: write _wake, execute, then call sleep()."""
        k = Kernel()
        k.ns["_wake"] = "user_message: compute 1+2+3"
        k.exec_operation("total = 1 + 2 + 3", frame_number=1)
        k.exec_operation("sleep()", frame_number=2)
        assert k.ns["total"] == 6
        assert k.ns["_sleeping"] is True

    def test_eval_expect_returns_verdict(self):
        """eval_expect() returns a Verdict."""
        from vessal.ark.shell.hull.cell.protocol import Verdict
        k = Kernel()
        k.exec_operation("x = 1", frame_number=1)
        verdict = k.eval_expect("assert x == 1")
        assert isinstance(verdict, Verdict)

    def test_eval_expect_passes(self):
        """eval_expect() returns passed == total for satisfied assertions."""
        k = Kernel()
        k.exec_operation("x = 42", frame_number=1)
        verdict = k.eval_expect("assert x == 42")
        assert verdict.total == 1
        assert verdict.passed == 1
        assert verdict.failures == ()

    def test_eval_expect_fails(self):
        """eval_expect() returns non-empty failures for failed assertions."""
        k = Kernel()
        k.exec_operation("x = 1", frame_number=1)
        verdict = k.eval_expect("assert x == 99")
        assert verdict.total == 1
        assert verdict.passed == 0
        assert len(verdict.failures) == 1

    def test_eval_expect_does_not_modify_ns(self):
        """eval_expect() evaluates on a shallow copy of the namespace; does not modify the real one."""
        k = Kernel()
        k.exec_operation("x = 1", frame_number=1)
        ns_keys_before = set(k.ns.keys())
        k.eval_expect("assert x == 1")
        assert set(k.ns.keys()) == ns_keys_before
        assert k.ns["x"] == 1

    def test_run_returns_none_and_commits_frame(self):
        """run(Pong) returns None; _frame_stream gets one frame committed; _frame increments by 1.

        ns["_frame"] is written by _commit_frame (not by exec_operation).
        """
        from vessal.ark.shell.hull.cell.protocol import Action, Pong
        from vessal.ark.shell.hull.cell.kernel.executor import ExecResult

        k = Kernel()
        frame_before = k.ns["_frame"]
        count_before = k.ns["_frame_stream"].hot_frame_count()

        pong = Pong(think="", action=Action(operation="x = 1", expect=""))

        mock_result = ExecResult(stdout="", diff="+x = 1", error=None)

        def _fake_exec(operation, frame_number, tracer=None):
            # exec_operation no longer writes ns["_frame"]; _commit_frame does
            return mock_result

        with patch.object(k, "exec_operation", side_effect=_fake_exec) as mock_exec:
            result = k.step(pong)

        assert result is None
        assert k.ns["_frame"] == frame_before + 1
        assert k.ns["_frame_stream"].hot_frame_count() == count_before + 1
        mock_exec.assert_called_once_with(
            "x = 1", frame_before + 1, None
        )


# ─────────────────────────────────────────────
# Bare expression value capture
# ─────────────────────────────────────────────

class TestExprCapture:
    """Bare expression value capture tests."""

    def test_bare_variable(self):
        """Value of a bare variable name is appended to _stdout."""
        ns = bare_ns()
        ns["x"] = 42
        execute("x", ns, frame_number=1)
        assert "42" in ns["_stdout"]

    def test_bare_expression_result(self):
        """Value of a bare expression (e.g. 1+2) is appended to _stdout."""
        ns = bare_ns()
        execute("1 + 2", ns, frame_number=1)
        assert "3" in ns["_stdout"]

    def test_assignment_no_capture(self):
        """Assignment statements do not trigger expression capture."""
        ns = bare_ns()
        execute("x = 42", ns, frame_number=1)
        assert ns["_stdout"] == ""

    def test_function_def_no_capture(self):
        """Function definitions do not trigger expression capture."""
        ns = bare_ns()
        execute("def foo(): pass", ns, frame_number=1)
        assert ns["_stdout"] == ""

    def test_print_plus_expr(self):
        """Both print output and bare expression value appear in _stdout."""
        ns = bare_ns()
        execute("print('out')\n1 + 1", ns, frame_number=1)
        assert "out" in ns["_stdout"]
        assert "2" in ns["_stdout"]

    def test_none_result_not_shown(self):
        """Expression value of None is not appended to _stdout."""
        ns = bare_ns()
        execute("None", ns, frame_number=1)
        assert ns["_stdout"] == ""

    def test_long_repr_truncated(self):
        """Oversized repr is truncated to _EXPR_REPR_MAX_LEN characters."""
        ns = bare_ns()
        ns["big"] = list(range(100000))
        execute("big", ns, frame_number=1)
        assert len(ns["_stdout"]) <= 2010  # repr + "\n"

    def test_syntax_error_passthrough(self):
        """Syntax errors are executed as-is; the error is captured in _error; no crash."""
        ns = bare_ns()
        execute("def foo(:\n    pass", ns, frame_number=1)
        assert ns["_error"] is not None

    def test_source_uses_original_action(self):
        """source_cache registers the original operation text (NOT the
        bare-expression-rewritten modified_operation). For pure-def code
        the two are identical, but the registration target is operation;
        verify via inspect.getsource."""
        import inspect
        ns = bare_ns()
        code = "def add(a, b):\n    return a + b"
        execute(code, ns, frame_number=1)
        src = inspect.getsource(ns["add"])
        assert "def add(a, b):" in src
        assert "return a + b" in src

    def test_expr_result_not_in_namespace(self):
        """_expr_result does not persist in namespace."""
        ns = bare_ns()
        execute("42", ns, frame_number=1)
        assert "_expr_result" not in ns

    def test_expr_result_not_in_diff(self):
        """_expr_result does not appear in _diff (system variable with _ prefix)."""
        ns = bare_ns()
        execute("42", ns, frame_number=1)
        assert "_expr_result" not in ns["_diff"]

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
        execute("print('hi')", ns, frame_number=1)
        assert ns["_stdout"] == "hi\n"


# ─────────────────────────────────────────────
# kernel.step() return value
# ─────────────────────────────────────────────

class TestStepReturnsNone:
    """kernel.step() no longer returns a Ping — it returns None."""

    def test_step_returns_none(self):
        """step() returns None after eliminating pre-render."""
        from vessal.ark.shell.hull.cell.kernel import Kernel
        from vessal.ark.shell.hull.cell.protocol import Action, Pong

        k = Kernel()
        k.ns["_system_prompt"] = "test"
        pong = Pong(think="t", action=Action(operation="x = 1", expect=""))
        result = k.step(pong)
        assert result is None, f"Expected None, got {type(result)}"


def test_restore_clears_incompatible_frame_stream(tmp_path):
    """restore() re-initializes _frame_stream when snapshot has incompatible type; no exception raised."""
    import cloudpickle
    from vessal.ark.shell.hull.cell.kernel import Kernel
    from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream

    # Create a snapshot with old-format _frame_log list (pre-FrameStream) instead of FrameStream
    snap_path = tmp_path / "test.snap"
    ns = {"_frame_log": [{"schema_version": 0}], "_system_prompt": "test"}
    with open(snap_path, "wb") as f:
        cloudpickle.dump({}, f)   # header: empty _loaded_skills
        cloudpickle.dump(ns, f)   # body: namespace

    # Restore and verify _frame_stream is a fresh FrameStream (incompatible format re-initialized)
    k = Kernel()
    k.restore(str(snap_path))

    assert isinstance(k.ns["_frame_stream"], FrameStream)
    assert k.ns["_frame_stream"].hot_frame_count() == 0


def test_restore_keeps_current_schema_frame_stream(tmp_path):
    """restore() preserves _frame_stream that is already a valid FrameStream."""
    import cloudpickle
    from vessal.ark.shell.hull.cell.kernel import Kernel
    from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream
    from vessal.ark.shell.hull.cell.protocol import FRAME_SCHEMA_VERSION

    # Build a FrameStream with one committed frame
    fs = FrameStream(k=16, n=8)
    fs.commit_frame({
        "schema_version": FRAME_SCHEMA_VERSION,
        "number": 1,
        "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
        "pong": {"think": "", "action": {"operation": "x = 1", "expect": ""}},
        "observation": {"stdout": "", "diff": "+x = 1", "error": None, "verdict": None},
    })

    snap_path = tmp_path / "test.snap"
    ns = {"_frame_stream": fs, "_system_prompt": "test"}
    with open(snap_path, "wb") as f:
        cloudpickle.dump({}, f)
        cloudpickle.dump(ns, f)

    k = Kernel()
    k.restore(str(snap_path))

    assert isinstance(k.ns["_frame_stream"], FrameStream)
    assert k.ns["_frame_stream"].hot_frame_count() == 1
    assert k.ns["_frame_stream"]._hot[0][0]["schema_version"] == FRAME_SCHEMA_VERSION


def test_restore_migrates_legacy_two_blob_format(tmp_path):
    """Legacy snapshot format: [skills_header_blob][ns_blob] is migrated to single-blob on restore.

    The legacy format wrote a header dict (first blob) followed by the real namespace dict
    (second blob). restore() detects remaining bytes after reading the first blob, discards
    the header, loads the namespace from the second blob, and rewrites the file in the
    current single-blob format so subsequent restores use the fast path.
    """
    import cloudpickle

    header_bytes = cloudpickle.dumps({"chat": {"parent_path": "/skills"}})
    ns_bytes = cloudpickle.dumps({"x": 99, "_sleeping": False})
    legacy_path = tmp_path / "legacy.pkl"
    legacy_path.write_bytes(header_bytes + ns_bytes)

    k = Kernel()
    k.restore(str(legacy_path))

    assert k.ns["x"] == 99

    # File must be rewritten in new single-blob format (fast path on subsequent restore)
    raw = legacy_path.read_bytes()
    import io
    buf = io.BytesIO(raw)
    restored_ns = cloudpickle.load(buf)
    assert buf.tell() == len(raw), "expected exactly one blob in migrated file"
    assert restored_ns["x"] == 99


def test_snapshot_tracks_dropped_keys(tmp_path):
    """snapshot() records dropped unpicklable keys in _dropped_keys.

    socket.socket cannot be pickled by cloudpickle; used to simulate connection objects.
    """
    import socket as _socket
    kernel = Kernel()
    kernel.ns["normal_var"] = 42
    sock = _socket.socket()
    kernel.ns["sock_handle"] = sock

    path = str(tmp_path / "snap.pkl")
    try:
        kernel.snapshot(path)
    finally:
        sock.close()

    kernel2 = Kernel()
    kernel2.restore(path)

    dropped = kernel2.ns.get("_dropped_keys", [])
    assert "normal_var" not in dropped
    assert kernel2.ns["normal_var"] == 42
    assert "sock_handle" in dropped


def test_restore_emits_reconstruction_signal(tmp_path):
    """After restore(), if _dropped_keys exist, the signal should include reconstruction hints."""
    kernel = Kernel()
    kernel.ns["x"] = 42
    kernel.ns["_dropped_keys"] = ["db_conn", "file_handle"]
    kernel.ns["_dropped_keys_context"] = {
        "db_conn": "db_conn = connect('postgres://...')",
        "file_handle": "file_handle = open('data.csv')",
    }

    path = str(tmp_path / "snap.pkl")
    kernel.snapshot(path)

    kernel2 = Kernel()
    kernel2.restore(path)
    kernel2.update_signals()

    signals = kernel2.ns.get("_signal_outputs", [])
    signal_text = "\n".join(body for _, body in signals)
    assert "db_conn" in signal_text


def test_init_namespace_has_compaction_defaults():
    from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
    k = Kernel()
    assert k.ns["_compaction_k"] == 16
    assert k.ns["_compaction_n"] == 8


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
        import inspect
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = Kernel()
        k.exec_operation("def add(a, b):\n    return a + b", frame_number=1)
        src = inspect.getsource(k.ns["add"])
        assert "def add(a, b):" in src
        assert "return a + b" in src

    def test_inspect_getsource_class_after_execute(self):
        import inspect
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = Kernel()
        k.exec_operation("class Bar:\n    def m(self):\n        return 1", frame_number=2)
        src = inspect.getsource(k.ns["Bar"])
        assert "class Bar:" in src
        assert "def m(self):" in src

    def test_inspect_getsource_async_function(self):
        import inspect
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = Kernel()
        k.exec_operation("async def waiter():\n    return 42", frame_number=3)
        src = inspect.getsource(k.ns["waiter"])
        assert "async def waiter" in src

    def test_inspect_getsource_decorated_function_includes_decorator(self):
        import inspect
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = Kernel()
        code = (
            "def my_decorator(fn):\n"
            "    return fn\n"
            "\n"
            "@my_decorator\n"
            "def decorated():\n"
            "    return 42"
        )
        k.exec_operation(code, frame_number=4)
        src = inspect.getsource(k.ns["decorated"])
        assert "@my_decorator" in src
        assert "def decorated" in src

    def test_inspect_getsource_distinct_per_function(self):
        """Two functions defined in the same operation each map to the
        single shared <frame-N> source; inspect.getsource returns the
        function's own definition span via the function's lineno."""
        import inspect
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = Kernel()
        code = "def foo():\n    return 1\n\ndef bar():\n    return 2"
        k.exec_operation(code, frame_number=5)
        foo_src = inspect.getsource(k.ns["foo"])
        bar_src = inspect.getsource(k.ns["bar"])
        assert "def foo" in foo_src
        assert "def bar" not in foo_src
        assert "def bar" in bar_src
        assert "def foo" not in bar_src
