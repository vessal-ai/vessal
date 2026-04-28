"""Spec §3.3: executor returns raw exception (with __traceback__ cleared)."""
from __future__ import annotations

from vessal.ark.shell.hull.cell.kernel.executor import execute


def test_clean_run_returns_no_error() -> None:
    G: dict = {}
    L: dict = {}
    result = execute("x = 1", G, L, frame_number=1)
    assert result.error is None
    assert L["x"] == 1


def test_runtime_error_yields_exception_object() -> None:
    G: dict = {}
    L: dict = {}
    result = execute("1 / 0", G, L, frame_number=1)
    assert isinstance(result.error, ZeroDivisionError)
    # __traceback__ must be None so cloudpickle can serialise it
    assert result.error.__traceback__ is None


def test_syntax_error_yields_syntax_error_object() -> None:
    G: dict = {}
    L: dict = {}
    result = execute("def (((", G, L, frame_number=1)
    assert isinstance(result.error, SyntaxError)
    assert result.error.__traceback__ is None


def test_exception_message_preserved() -> None:
    G: dict = {}
    L: dict = {}
    result = execute("raise ValueError('boom')", G, L, frame_number=1)
    assert isinstance(result.error, ValueError)
    assert str(result.error) == "boom"
