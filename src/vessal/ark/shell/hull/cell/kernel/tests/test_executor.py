"""tests/unit/test_executor.py — Unit tests for executor side-effect variables, diff, and _ns_meta."""

from __future__ import annotations

import pytest

from vessal.ark.shell.hull.cell.kernel.executor import ExecResult, execute, is_user_var


def _ns() -> dict:
    """Minimal namespace containing only the system variables required by executor."""
    return {
        "_frame": 0,
        "_operation": "",
        "_stdout": "",
        "_error": None,
        "_diff": "",
        "_ns_meta": {},
        "_frame_log": [],
    }


# ────────────────────────────────────────────── side-effect variables


class TestExecuteSideEffects:
    def test_returns_exec_result(self):
        """execute() returns an ExecResult, not None."""
        ns = _ns()
        result = execute("x = 1", ns, frame_number=1)
        assert isinstance(result, ExecResult)

    def test_exec_result_fields_on_success(self):
        """ExecResult fields are correct after successful execution."""
        ns = _ns()
        result = execute("x = 1", ns, frame_number=1)
        assert result.stdout == ""
        assert result.diff != ""  # x = 1 produces a diff
        assert result.error is None

    def test_exec_result_on_error(self):
        """ExecResult.error is not None when execution raises an exception."""
        ns = _ns()
        result = execute("raise ValueError('boom')", ns, frame_number=1)
        assert result.error is not None
        assert "ValueError" in result.error

    def test_operation_recorded(self):
        """ns['_operation'] stores the raw code string after execution."""
        ns = _ns()
        execute("x = 1", ns, frame_number=1)
        assert ns["_operation"] == "x = 1"

    def test_action_key_not_used(self):
        """The legacy _action key is no longer written by execute."""
        ns = _ns()
        execute("x = 1", ns, frame_number=1)
        # _action should not be written by execute (_operation replaced it after Phase 2)
        # if _action was not in ns originally, it should not appear
        assert "_action" not in ns

    def test_stdout_captured(self):
        ns = _ns()
        execute("print('hello')", ns, frame_number=1)
        assert "hello" in ns["_stdout"]

    def test_error_none_on_success(self):
        ns = _ns()
        execute("x = 1", ns, frame_number=1)
        assert ns["_error"] is None

    def test_error_set_on_exception(self):
        ns = _ns()
        execute("raise ValueError('boom')", ns, frame_number=1)
        assert ns["_error"] is not None
        assert "ValueError" in ns["_error"]
        assert "boom" in ns["_error"]

    def test_empty_action_resets_vars(self):
        ns = _ns()
        ns["_operation"] = "old"
        ns["_stdout"] = "old"
        ns["_error"] = "old"
        execute("", ns, frame_number=1)
        assert ns["_operation"] == ""
        assert ns["_stdout"] == ""
        assert ns["_error"] is None

    def test_none_action_resets_vars(self):
        ns = _ns()
        execute(None, ns, frame_number=1)
        assert ns["_operation"] == ""

    def test_bare_expression_appended_to_stdout(self):
        """Bare expression result is appended to _stdout (Jupyter style)."""
        ns = _ns()
        execute("1 + 2", ns, frame_number=1)
        assert "3" in ns["_stdout"]

    def test_bare_none_not_appended(self):
        """Bare expression value of None is not appended to _stdout."""
        ns = _ns()
        execute("None", ns, frame_number=1)
        assert ns["_stdout"] == ""

    def test_keyboard_interrupt_propagates(self):
        ns = _ns()
        with pytest.raises(KeyboardInterrupt):
            execute("raise KeyboardInterrupt()", ns, frame_number=1)

    def test_frame_not_written_by_executor(self):
        """execute() does not write ns['_frame']; that is _commit_frame's responsibility."""
        ns = _ns()
        initial = ns["_frame"]
        execute("x = 1", ns, frame_number=42)
        assert ns["_frame"] == initial

    def test_empty_action_returns_exec_result(self):
        """Empty operation also returns an ExecResult."""
        ns = _ns()
        result = execute("", ns, frame_number=1)
        assert isinstance(result, ExecResult)
        assert result.stdout == ""
        assert result.diff == ""
        assert result.error is None

    def test_exec_result_matches_ns_state(self):
        """ExecResult field values match the corresponding system variables in ns."""
        ns = _ns()
        result = execute("print('hi')\nx = 1", ns, frame_number=1)
        assert result.stdout == ns["_stdout"]
        assert result.diff == ns["_diff"]
        assert result.error == ns["_error"]


# ────────────────────────────────────────────── diff calculation


class TestDiffCalculation:
    def test_new_variable_diff(self):
        ns = _ns()
        execute("alpha = 42", ns, frame_number=1)
        assert "+alpha = 42" in ns["_diff"]

    def test_modified_variable_diff(self):
        ns = _ns()
        ns["x"] = 1
        execute("x = 99", ns, frame_number=1)
        assert "-x = 1" in ns["_diff"]
        assert "+x = 99" in ns["_diff"]

    def test_deleted_variable_diff(self):
        ns = _ns()
        ns["x"] = 1
        execute("del x", ns, frame_number=1)
        assert "-x = 1" in ns["_diff"]

    def test_no_change_empty_diff(self):
        ns = _ns()
        execute("pass", ns, frame_number=1)
        assert ns["_diff"] == ""

    def test_system_vars_excluded_from_diff(self):
        ns = _ns()
        execute("_internal = 'hidden'", ns, frame_number=1)
        assert "_internal" not in ns["_diff"]

    def test_multiple_vars_sorted(self):
        ns = _ns()
        execute("z = 1\na = 2", ns, frame_number=1)
        diff_lines = ns["_diff"].splitlines()
        names = [line[1:].split(" =")[0] for line in diff_lines]
        assert names == sorted(names)


# ────────────────────────────────────────────── _ns_meta updates


class TestNsMetaUpdate:
    def test_new_var_gets_meta(self):
        ns = _ns()
        execute("my_var = 42", ns, frame_number=1)
        assert "my_var" in ns["_ns_meta"]
        meta = ns["_ns_meta"]["my_var"]
        assert meta["type"] == "int"
        assert meta["created"] == 1  # frame_number
        assert meta["accesses"] == 1

    def test_modified_var_increments_accesses(self):
        ns = _ns()
        execute("x = 1", ns, frame_number=1)
        execute("x = 2", ns, frame_number=2)
        assert ns["_ns_meta"]["x"]["accesses"] == 2

    def test_deleted_var_removed_from_meta(self):
        ns = _ns()
        execute("temp = 'bye'", ns, frame_number=1)
        assert "temp" in ns["_ns_meta"]
        execute("del temp", ns, frame_number=2)
        assert "temp" not in ns["_ns_meta"]

    def test_system_vars_excluded_from_meta(self):
        ns = _ns()
        execute("_sys = 'internal'", ns, frame_number=1)
        assert "_sys" not in ns["_ns_meta"]

    def test_size_recorded(self):
        ns = _ns()
        execute("big = list(range(1000))", ns, frame_number=1)
        assert ns["_ns_meta"]["big"]["size"] > 0


# ────────────────────────────────────────────── builtins protection


class TestBuiltinsProtection:
    """Protected keys deleted by agent code are restored after exec."""

    def test_del_sleep_is_restored(self):
        """sleep remains in namespace after agent executes del sleep."""
        ns = _ns()
        ns["sleep"] = lambda: None
        ns["_protected_keys"] = list(ns.keys())
        execute("del sleep", ns, frame_number=1)
        assert "sleep" in ns
        assert callable(ns["sleep"])

    def test_del_system_var_is_restored(self):
        """_error remains in namespace after agent executes del _error."""
        ns = _ns()
        ns["_protected_keys"] = list(ns.keys())
        execute("del _error", ns, frame_number=1)
        assert "_error" in ns

    def test_restore_prints_warning(self):
        """stdout contains notification info when variables are restored."""
        ns = _ns()
        ns["sleep"] = lambda: None
        ns["_protected_keys"] = list(ns.keys())
        result = execute("del sleep", ns, frame_number=1)
        assert "automatically restored" in result.stdout
        assert "sleep" in result.stdout

    def test_user_del_not_affected(self):
        """Deleting a user variable is not affected (not restored)."""
        ns = _ns()
        ns["_protected_keys"] = list(ns.keys())
        ns["my_var"] = 42  # user variable, not in _protected_keys
        execute("del my_var", ns, frame_number=1)
        assert "my_var" not in ns

    def test_multiple_del_all_restored(self):
        """All protected keys are restored when multiple are deleted at once."""
        ns = _ns()
        ns["sleep"] = lambda: None
        ns["skills"] = "fake_skills"
        ns["_protected_keys"] = list(ns.keys())
        execute("del sleep, skills", ns, frame_number=1)
        assert "sleep" in ns
        assert "skills" in ns


# ────────────────────────────────────────────── ErrorRecord writing


class TestErrorRecording:
    """executor writes runtime errors and builtin restores to _errors."""

    def test_runtime_error_recorded(self):
        from vessal.ark.shell.hull.cell.protocol import ErrorRecord
        ns = _ns()
        ns["_errors"] = []
        ns["_protected_keys"] = list(ns.keys())
        execute("raise ValueError('boom')", ns, frame_number=1)
        errors = ns["_errors"]
        assert len(errors) == 1
        assert errors[0].type == "runtime"
        assert "ValueError" in errors[0].message

    def test_builtin_restore_recorded(self):
        from vessal.ark.shell.hull.cell.protocol import ErrorRecord
        ns = _ns()
        ns["sleep"] = lambda: None
        ns["_errors"] = []
        ns["_protected_keys"] = list(ns.keys())
        execute("del sleep", ns, frame_number=1)
        errors = ns["_errors"]
        assert any(e.type == "builtin_restored" for e in errors)


import inspect
import linecache


class TestLinecacheRegistration:
    """executor registers operation source into linecache under '<frame-N>' so
    inspect.getsource works on classes/functions defined in operation."""

    def _clear(self, n: int) -> None:
        linecache.cache.pop(f"<frame-{n}>", None)

    def test_operation_lines_in_linecache(self):
        ns = _ns()
        self._clear(42)
        execute("x = 1\ny = 2\n", ns, frame_number=42)
        assert linecache.getlines("<frame-42>") == ["x = 1\n", "y = 2\n"]

    def test_inspect_getsource_works_on_class_defined_in_operation(self):
        """The whole point of the PR — agent code defines a class, inspect can fetch source."""
        ns = _ns()
        self._clear(42)
        execute(
            "class Planner:\n    def plan(self):\n        return [1, 2, 3]\n",
            ns,
            frame_number=42,
        )
        Planner = ns["Planner"]
        src = inspect.getsource(Planner)
        assert "class Planner" in src
        assert "return [1, 2, 3]" in src

    def test_co_filename_is_frame_n(self):
        """compile() uses <frame-N>; functions defined in operation inherit it via co_filename."""
        ns = _ns()
        self._clear(42)
        execute("def helper():\n    return 99\n", ns, frame_number=42)
        assert ns["helper"].__code__.co_filename == "<frame-42>"

    def test_traceback_text_references_frame_n(self):
        """Tracebacks now point at <frame-N>, not <string>."""
        ns = _ns()
        self._clear(42)
        execute("raise ValueError('boom')\n", ns, frame_number=42)
        err = ns["_error"]
        assert err is not None
        assert '"<frame-42>"' in err

    def test_empty_operation_does_not_register(self):
        """No-op operation does not pollute linecache."""
        self._clear(99)
        ns = _ns()
        execute("", ns, frame_number=99)
        assert "<frame-99>" not in linecache.cache
