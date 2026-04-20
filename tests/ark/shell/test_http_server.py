"""test_http_server — contract: disconnect-class exceptions never print a
traceback on stderr; all other exceptions fall through to stdlib default."""
from __future__ import annotations

import io
import logging
import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def safe_classes():
    from vessal.ark.shell.http_server import SafeHTTPServer, SafeThreadingHTTPServer
    return SafeHTTPServer, SafeThreadingHTTPServer


def _dummy_instance(cls):
    return cls.__new__(cls)


@pytest.mark.parametrize(
    "exc",
    [
        ConnectionResetError("reset by peer"),
        BrokenPipeError("broken pipe"),
        ConnectionAbortedError("aborted"),
        TimeoutError("timeout"),
    ],
)
def test_disconnect_errors_demoted_to_debug_log(safe_classes, exc, caplog, capsys):
    SafeHTTPServer, _ = safe_classes
    server = _dummy_instance(SafeHTTPServer)
    with caplog.at_level(logging.DEBUG, logger="vessal.shell.http"):
        try:
            raise exc
        except type(exc):
            server.handle_error(request=MagicMock(), client_address=("127.0.0.1", 12345))

    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out
    assert any(
        record.levelno == logging.DEBUG and type(exc).__name__ in record.getMessage()
        for record in caplog.records
    ), caplog.records


def test_unexpected_error_falls_through_to_super(safe_classes, capsys):
    SafeHTTPServer, _ = safe_classes
    server = _dummy_instance(SafeHTTPServer)
    try:
        raise RuntimeError("genuinely broken")
    except RuntimeError:
        server.handle_error(request=MagicMock(), client_address=("127.0.0.1", 12345))

    captured = capsys.readouterr()
    assert "Traceback" in captured.err
    assert "RuntimeError" in captured.err
    assert "genuinely broken" in captured.err


def test_threading_variant_shares_contract(safe_classes, caplog, capsys):
    _, SafeThreadingHTTPServer = safe_classes
    server = _dummy_instance(SafeThreadingHTTPServer)
    with caplog.at_level(logging.DEBUG, logger="vessal.shell.http"):
        try:
            raise ConnectionResetError("reset")
        except ConnectionResetError:
            server.handle_error(request=MagicMock(), client_address=("127.0.0.1", 0))
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
