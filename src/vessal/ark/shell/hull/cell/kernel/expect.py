"""expect.py — Expect assertion validation and evaluation: AST safety checks and per-statement evaluation, returning a Verdict."""
# Pure functions, no side effects, no state.
#
# Public interface:
#   ExpectValidationError  base exception for expect validation failure
#   ExpectSyntaxError      expect syntax error (ast.parse failed)
#   ExpectUnsafeError      expect contains disallowed syntax constructs
#   validate_expect_ast()  validate AST legality, return ast.Module
#   evaluate_expect()      evaluate on a shallow copy of namespace, return Verdict
#
# Design constraints:
#   evaluate_expect() never raises — all errors are collected into Verdict.failures.
#   Each assert is evaluated independently without short-circuiting; all failures
#   are collected.
#
# Not responsible for: code execution (executor), frame management (kernel).

from __future__ import annotations

import ast
import textwrap
from typing import Any

from vessal.ark.shell.hull.cell.protocol import Verdict, VerdictFailure
from vessal.ark.shell.hull.cell.kernel import source_cache


class ExpectValidationError(ValueError):
    """expect code is invalid.

    Subclass of ValueError; the error message includes the specific reason.
    """


class ExpectSyntaxError(ExpectValidationError):
    """expect code has a syntax error (ast.parse failed)."""
    pass


class ExpectUnsafeError(ExpectValidationError):
    """expect code contains disallowed syntax constructs."""
    pass


def _check_no_forbidden_nodes(tree: ast.Module) -> None:
    """Recursively check the AST tree for forbidden node types.

    Forbidden: walrus operator (:=).
    Allowed: arbitrary function calls, attribute access, subscript access —
    expect is read-only observation; assignments are blocked by the top-level
    assert-only check; walrus is the only exception that can assign within an
    expression.

    Args:
        tree: Parsed AST module.

    Raises:
        ExpectValidationError: When a forbidden node is found; includes specific reason.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.NamedExpr):
            raise ExpectUnsafeError(
                "Walrus operator (:=) is not allowed in expect"
            )


def validate_expect_ast(expect: str) -> ast.Module:
    """Validate the AST legality of expect code.

    Only top-level assert statements are allowed (assert expr or assert expr, message).
    No other statements or forbidden expression nodes are permitted.

    Args:
        expect: expect code string, may be multi-line.

    Returns:
        Parsed ast.Module for subsequent per-statement execution.

    Raises:
        ExpectSyntaxError: Python SyntaxError (syntax error).
        ExpectUnsafeError: Top-level non-assert statement found, or forbidden AST nodes
            (import, assignment, method call, walrus, etc.) found.
    """
    # Remove common indentation to prevent SyntaxError from indentation
    dedented = textwrap.dedent(expect)

    try:
        tree = ast.parse(dedented, mode="exec")
    except SyntaxError as exc:
        raise ExpectSyntaxError(
            f"expect code syntax error: {exc.msg} (line {exc.lineno})"
        ) from exc

    # Only assert statements are allowed at the top level
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assert):
            stmt_type = type(stmt).__name__
            raise ExpectUnsafeError(
                f"expect only allows assert statements; found illegal top-level statement: {stmt_type}"
            )

    # Check for forbidden nodes (including nested)
    _check_no_forbidden_nodes(tree)

    return tree


def _assert_to_source(node: ast.Assert) -> str:
    """Reconstruct an Assert node as a readable source string (best-effort).

    Args:
        node: ast.Assert node.

    Returns:
        Readable string, e.g. "assert x == 1" or "assert x > 0, 'msg'".
    """
    try:
        return ast.unparse(node)
    except Exception:
        return "<assert>"


def evaluate_expect(expect: str, ns: dict[str, Any], frame_number: int) -> Verdict:
    """Evaluate expect assertions on a shallow copy of the namespace.

    Evaluation steps:
    1. Call validate_expect_ast() to check syntax and safety.
    2. Shallow-copy ns to prevent expect from modifying the execution namespace.
    3. Compile + exec each assert independently, collect all failures without
       short-circuiting.
    4. Return Verdict.

    This function never raises — all errors are collected into the failures list.

    Args:
        expect: expect code string.
        ns: Namespace after operation execution (shallow-copied; original not modified).
        frame_number: Current frame number; used as the linecache filename suffix
            (`<frame-{n}-expect>`) so inspect.getsource and traceback show
            the right context.

    Returns:
        Verdict containing total/passed/failures.

    Side effects:
        Does not modify the passed-in ns. The shallow-copy may be read by expect
        code but should not be written to (validate_expect_ast blocks assignment
        statements).
    """
    # Register the expect text into linecache so inspect.getsource and
    # traceback line printing work for any functions/classes in expect.
    source_cache.register(frame_number, None, expect)
    # Validation phase: syntax/safety errors → overall failure
    try:
        tree = validate_expect_ast(expect)
    except ExpectSyntaxError as exc:
        failure = VerdictFailure(
            kind="expect_syntax_error",
            assertion=expect.strip(),
            message=str(exc),
        )
        return Verdict(total=0, passed=0, failures=(failure,))
    except ExpectUnsafeError as exc:
        failure = VerdictFailure(
            kind="expect_unsafe_error",
            assertion=expect.strip(),
            message=str(exc),
        )
        return Verdict(total=0, passed=0, failures=(failure,))

    assert_stmts: list[ast.Assert] = [
        stmt for stmt in tree.body if isinstance(stmt, ast.Assert)
    ]
    total = len(assert_stmts)

    if total == 0:
        return Verdict(total=0, passed=0, failures=())

    # Shallow-copy namespace: prevent expect from writing to the execution environment
    eval_ns = dict(ns)

    failures: list[VerdictFailure] = []

    for stmt in assert_stmts:
        source = _assert_to_source(stmt)
        # Build a mini-module containing only this assert, compile it separately
        mini_module = ast.Module(body=[stmt], type_ignores=[])
        ast.fix_missing_locations(mini_module)
        try:
            code = compile(mini_module, filename=f"<frame-{frame_number}-expect>", mode="exec")
            exec(code, eval_ns)  # noqa: S102
        except AssertionError as exc:
            msg = str(exc) if str(exc) else f"Assertion is False: {source}"
            failures.append(VerdictFailure(
                kind="assertion_failed",
                assertion=source,
                message=msg,
            ))
        except Exception as exc:  # noqa: BLE001
            failures.append(VerdictFailure(
                kind="expect_runtime_error",
                assertion=source,
                message=f"{type(exc).__name__}: {exc}",
            ))

    passed = total - len(failures)
    return Verdict(
        total=total,
        passed=passed,
        failures=tuple(failures),
    )
