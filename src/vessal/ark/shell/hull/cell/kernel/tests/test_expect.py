# tests/unit/test_expect.py — expect validation and evaluation tests
#
# Coverage:
#   TestValidateExpectAst              AST validation: allow/reject various syntax constructs
#   TestEvaluateExpect                 Evaluation: pass/fail/multi/no-short-circuit/never-raises
#   TestExpectLinecacheRegistration    linecache registration under <frame-N-expect>

import linecache
import sys

import pytest

from vessal.ark.shell.hull.cell.kernel.expect import ExpectValidationError, evaluate_expect, validate_expect_ast
from vessal.ark.shell.hull.cell.protocol import Verdict, VerdictFailure


# ─────────────────────────────────────────────
# TestValidateExpectAst
# ─────────────────────────────────────────────


class TestValidateExpectAst:
    """White-box tests for validate_expect_ast."""

    # ── valid cases ──

    def test_single_assert(self):
        """Single assert statement is valid."""
        tree = validate_expect_ast("assert x == 1")
        assert len(tree.body) == 1

    def test_multiple_asserts(self):
        """Multiple assert statements are valid."""
        code = "assert x > 0\nassert y < 100\nassert z == 'ok'"
        tree = validate_expect_ast(code)
        assert len(tree.body) == 3

    def test_assert_with_message(self):
        """assert expr, msg form is valid."""
        tree = validate_expect_ast("assert x == 1, 'x should be 1'")
        assert len(tree.body) == 1

    def test_whitelist_len_call(self):
        """len() is in the allowlist and is valid."""
        validate_expect_ast("assert len(items) > 0")

    def test_whitelist_all_call(self):
        """all() is in the allowlist and is valid."""
        validate_expect_ast("assert all(x > 0 for x in items)")

    def test_whitelist_isinstance_call(self):
        """isinstance() is in the allowlist and is valid."""
        validate_expect_ast("assert isinstance(x, int)")

    def test_whitelist_sorted_call(self):
        """sorted() is in the allowlist and is valid."""
        validate_expect_ast("assert sorted(items) == [1, 2, 3]")

    def test_whitelist_sum_min_max(self):
        """sum/min/max are all in the allowlist and are valid."""
        validate_expect_ast("assert sum(nums) == 10\nassert min(nums) >= 0\nassert max(nums) <= 100")

    def test_indented_code_handled(self):
        """Indented code (handled by textwrap.dedent) is valid."""
        code = "    assert x == 1\n    assert y == 2"
        validate_expect_ast(code)

    # ── invalid cases: forbidden top-level statements ──

    def test_rejects_import(self):
        """import statement is not valid."""
        with pytest.raises(ExpectValidationError):
            validate_expect_ast("import os")

    def test_rejects_from_import(self):
        """from ... import is not valid."""
        with pytest.raises(ExpectValidationError):
            validate_expect_ast("from os import path")

    def test_rejects_assignment(self):
        """Assignment statement is not valid."""
        with pytest.raises(ExpectValidationError):
            validate_expect_ast("x = 1")

    def test_rejects_augmented_assignment(self):
        """Augmented assignment is not valid."""
        with pytest.raises(ExpectValidationError):
            validate_expect_ast("x += 1")

    def test_rejects_function_def(self):
        """Function definition is not valid."""
        with pytest.raises(ExpectValidationError):
            validate_expect_ast("def foo(): pass")

    def test_rejects_class_def(self):
        """Class definition is not valid."""
        with pytest.raises(ExpectValidationError):
            validate_expect_ast("class Foo: pass")

    def test_rejects_for_loop(self):
        """for loop is not valid."""
        with pytest.raises(ExpectValidationError):
            validate_expect_ast("for i in range(10):\n    assert i < 10")

    def test_rejects_while_loop(self):
        """while loop is not valid."""
        with pytest.raises(ExpectValidationError):
            validate_expect_ast("while True:\n    pass")

    def test_rejects_try(self):
        """try statement is not valid."""
        with pytest.raises(ExpectValidationError):
            validate_expect_ast("try:\n    pass\nexcept:\n    pass")

    def test_rejects_raise(self):
        """raise is not valid."""
        with pytest.raises(ExpectValidationError):
            validate_expect_ast("raise ValueError('err')")

    def test_rejects_delete(self):
        """del is not valid."""
        with pytest.raises(ExpectValidationError):
            validate_expect_ast("del x")

    # ── valid cases: attribute access and arbitrary function calls are allowed ──

    def test_allows_attribute_method_call(self):
        """Attribute method call (x.strip()) is valid."""
        validate_expect_ast("assert x.strip() == 'hello'")

    def test_allows_attribute_access(self):
        """Attribute access (obj.attr) is valid."""
        validate_expect_ast("assert obj.value == 1")

    def test_allows_custom_function_call(self):
        """Calling a custom function is valid."""
        validate_expect_ast("assert my_func(x) == 1")

    def test_allows_non_builtin_call(self):
        """Calling a function with any name (e.g. print) is valid."""
        validate_expect_ast("assert print('x') is None")

    def test_allows_subscript_call(self):
        """Subscript after call is valid, e.g. tasks.get_task(id)['status']."""
        validate_expect_ast("assert tasks.get_task(t_root)['status'] == 'active'")

    # ── invalid cases: walrus operator ──

    def test_rejects_walrus_operator(self):
        """Walrus operator := is not valid."""
        with pytest.raises(ExpectValidationError):
            validate_expect_ast("assert (n := len(x)) > 0")

    # ── syntax errors ──

    def test_rejects_syntax_error(self):
        """Python syntax error raises ExpectValidationError."""
        with pytest.raises(ExpectValidationError, match="syntax error"):
            validate_expect_ast("assert x ==")

    def test_returns_ast_module(self):
        """Valid expect returns an ast.Module object."""
        import ast
        tree = validate_expect_ast("assert True")
        assert isinstance(tree, ast.Module)


# ─────────────────────────────────────────────
# TestEvaluateExpect
# ─────────────────────────────────────────────


class TestEvaluateExpect:
    """Behavioral tests for evaluate_expect."""

    # ── all pass ──

    def test_all_pass(self):
        """When all assertions pass, passed == total and failures is empty."""
        ns = {"x": 1, "y": 2}
        result = evaluate_expect("assert x == 1\nassert y == 2", ns, frame_number=1)
        assert isinstance(result, Verdict)
        assert result.total == 2
        assert result.passed == 2
        assert result.failures == ()

    def test_single_pass(self):
        """Single passing assertion."""
        ns = {"value": 42}
        result = evaluate_expect("assert value == 42", ns, frame_number=1)
        assert result.total == 1
        assert result.passed == 1

    # ── failure cases ──

    def test_single_failure(self):
        """Single assertion failure: failures contains one record with kind == assertion_failed."""
        ns = {"x": 0}
        result = evaluate_expect("assert x == 1", ns, frame_number=1)
        assert result.total == 1
        assert result.passed == 0
        assert len(result.failures) == 1
        assert result.failures[0].kind == "assertion_failed"

    def test_assertion_failure_with_message(self):
        """assert expr, msg failure: message contains the custom error string."""
        ns = {"x": 0}
        result = evaluate_expect("assert x > 0, 'x must be positive'", ns, frame_number=1)
        assert result.failures[0].message == "x must be positive"

    # ── no short-circuit: collect all failures ──

    def test_multiple_failures_no_short_circuit(self):
        """Multiple assertion failures are all collected without short-circuiting."""
        ns = {"a": 0, "b": 0}
        code = "assert a == 1\nassert b == 2\nassert a + b == 3"
        result = evaluate_expect(code, ns, frame_number=1)
        assert result.total == 3
        assert result.passed == 0
        assert len(result.failures) == 3

    def test_partial_failures(self):
        """With partial failures, passed and failures counts are correct."""
        ns = {"x": 1, "y": 0}
        code = "assert x == 1\nassert y == 1"
        result = evaluate_expect(code, ns, frame_number=1)
        assert result.total == 2
        assert result.passed == 1
        assert len(result.failures) == 1
        assert result.failures[0].kind == "assertion_failed"

    # ── syntax error → expect_syntax_error ──

    def test_syntax_error_produces_syntax_failure(self):
        """Syntax error returns Verdict with kind == expect_syntax_error."""
        result = evaluate_expect("assert x ==", {"x": 1}, frame_number=1)
        assert isinstance(result, Verdict)
        assert result.total == 0
        assert result.passed == 0
        assert result.failures[0].kind == "expect_syntax_error"

    # ── safety violation → expect_unsafe_error ──

    def test_unsafe_import_produces_unsafe_failure(self):
        """import statement returns Verdict with kind == expect_unsafe_error."""
        result = evaluate_expect("import os", {}, frame_number=1)
        assert isinstance(result, Verdict)
        assert result.failures[0].kind == "expect_unsafe_error"

    def test_attribute_method_call_evaluates_correctly(self):
        """Attribute method call evaluates correctly, not an unsafe_error."""
        result = evaluate_expect("assert x.strip() == 'hi'", {"x": "hi "}, frame_number=1)
        assert result.total == 1
        assert result.passed == 1
        assert not result.failures

    # ── runtime error → expect_runtime_error ──

    def test_runtime_error_produces_runtime_failure(self):
        """Non-AssertionError runtime exception has kind == expect_runtime_error."""
        # assert 1 / 0 raises ZeroDivisionError during eval, not AssertionError
        result = evaluate_expect("assert 1 / 0", {}, frame_number=1)
        assert result.failures[0].kind == "expect_runtime_error"
        assert result.total == 1
        assert result.passed == 0

    def test_name_error_is_runtime_failure(self):
        """Accessing a missing variable has kind == expect_runtime_error."""
        ns = {}
        result = evaluate_expect("assert missing_var == 1", ns, frame_number=1)
        assert result.total == 1
        assert result.passed == 0
        assert result.failures[0].kind == "expect_runtime_error"
        assert "NameError" in result.failures[0].message

    def test_type_error_in_comparison_is_runtime_failure(self):
        """TypeError (e.g. comparing incomparable types) has kind == expect_runtime_error."""
        ns = {"x": object()}
        # sorted() needs comparable items
        result = evaluate_expect("assert sorted([x, 1]) == [1, x]", ns, frame_number=1)
        # This raises TypeError: '<' not supported
        assert result.failures[0].kind == "expect_runtime_error"

    # ── evaluate_expect never raises ──

    def test_never_raises_on_syntax_error(self):
        """Syntax error never raises; returns Verdict."""
        result = evaluate_expect("assert (", {}, frame_number=1)
        assert isinstance(result, Verdict)

    def test_never_raises_on_unsafe_code(self):
        """Illegal code never raises; returns Verdict."""
        result = evaluate_expect("import sys\nassert sys.version", {}, frame_number=1)
        assert isinstance(result, Verdict)

    def test_never_raises_on_runtime_error(self):
        """Runtime error never raises; returns Verdict."""
        result = evaluate_expect("assert 1/0 == 0", {}, frame_number=1)
        assert isinstance(result, Verdict)

    def test_never_raises_on_exception_in_exec(self):
        """Any exception inside exec is caught as expect_runtime_error and not propagated."""
        ns = {}
        result = evaluate_expect("assert nonexistent_func()", ns, frame_number=1)
        assert isinstance(result, Verdict)
        assert result.passed == 0

    # ── namespace isolation ──

    def test_does_not_modify_ns(self):
        """evaluate_expect does not modify the passed-in ns (uses a shallow copy)."""
        ns = {"x": 1}
        ns_before = dict(ns)
        evaluate_expect("assert x == 1", ns, frame_number=1)
        assert ns == ns_before

    # ── edge case: empty string ──

    def test_empty_expect_not_called_via_evaluate(self):
        """Empty expect returns Verdict(total=0, passed=0, failures=())."""
        result = evaluate_expect("", {}, frame_number=1)
        assert result.total == 0
        assert result.passed == 0
        assert result.failures == ()

    # ── assertion field in failures ──

    def test_assertion_field_contains_code(self):
        """failure.assertion contains the original assertion code string."""
        ns = {"x": 0}
        result = evaluate_expect("assert x == 1", ns, frame_number=1)
        assert "assert" in result.failures[0].assertion


# ─────────────────────────────────────────────
# TestExpectLinecacheRegistration
# ─────────────────────────────────────────────


class TestExpectLinecacheRegistration:
    """evaluate_expect registers expect source under <frame-N-expect>."""

    def _clear(self, n: int) -> None:
        linecache.cache.pop(f"<frame-{n}-expect>", None)
        sys.modules.pop(f"<frame-{n}-expect>", None)

    def test_expect_lines_in_linecache(self):
        self._clear(7)
        evaluate_expect("assert x == 1\n", {"x": 1}, frame_number=7)
        assert linecache.getlines("<frame-7-expect>") == ["assert x == 1\n"]

    def test_filename_uses_single_bracket_pair(self):
        """Filename is <frame-7-expect>, NOT <frame-7>-expect> (single pair, dash-joined)."""
        self._clear(7)
        evaluate_expect("assert x == 1\n", {"x": 1}, frame_number=7)
        assert "<frame-7-expect>" in linecache.cache
        assert "<frame-7>-expect>" not in linecache.cache

    def test_assertion_failure_traceback_references_frame_n_expect(self):
        """Failed assert produces a Verdict.failure; linecache key must exist."""
        self._clear(7)
        verdict = evaluate_expect("assert x == 999\n", {"x": 1}, frame_number=7)
        assert len(verdict.failures) == 1
        assert "<frame-7-expect>" in linecache.cache

    def test_empty_expect_does_not_register(self):
        self._clear(7)
        evaluate_expect("", {"x": 1}, frame_number=7)
        assert "<frame-7-expect>" not in linecache.cache
