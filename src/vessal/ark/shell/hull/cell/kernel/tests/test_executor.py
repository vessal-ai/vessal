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

    def test_frame_set_before_execution(self):
        """ns['_frame'] is set to frame_number before execution so operation code can read it."""
        ns = _ns()
        # code reads _frame and assigns it to seen_frame
        execute("seen_frame = _frame", ns, frame_number=7)
        assert ns["seen_frame"] == 7

    def test_frame_number_reflected_in_ns(self):
        """ns['_frame'] == frame_number after execute()."""
        ns = _ns()
        execute("x = 1", ns, frame_number=42)
        assert ns["_frame"] == 42

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
