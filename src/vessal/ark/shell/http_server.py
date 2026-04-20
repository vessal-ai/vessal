"""http_server.py — shared HTTP server base classes for Vessal.

Purpose:
    Every stdlib ``HTTPServer`` / ``ThreadingHTTPServer`` in the repo must
    inherit from one of the classes defined here. That gives us one, and
    only one, place that decides how transport-level client disconnects are
    reported — see ``handle_error`` below.

Contract:
    ``ConnectionResetError``, ``BrokenPipeError``, ``ConnectionAbortedError``
    and ``TimeoutError`` raised out of a request handler are expected
    consequences of HTTP/1.1 keep-alive + TCP (the client closed its socket
    between requests). They are logged at DEBUG on ``vessal.shell.http`` and
    not printed to stderr. Every other exception falls through to the stdlib
    default, which prints a full traceback — that behavior is retained on
    purpose so real bugs stay loud.

Enforcement:
    ``tests/architecture/test_no_raw_http_server.py`` fails CI if any
    production file constructs ``http.server.HTTPServer`` or
    ``http.server.ThreadingHTTPServer`` directly.
"""
from __future__ import annotations

import http.server
import logging
import sys

_logger = logging.getLogger("vessal.shell.http")

_QUIET_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionResetError,
    BrokenPipeError,
    ConnectionAbortedError,
    TimeoutError,
)


class _HandleErrorMixin:
    """Shared ``handle_error`` policy for the Vessal HTTP server family."""

    def handle_error(self, request, client_address):  # type: ignore[override]
        exc = sys.exc_info()[1]
        if isinstance(exc, _QUIET_EXCEPTIONS):
            _logger.debug(
                "client disconnected (%s) from %s",
                type(exc).__name__,
                client_address,
            )
            return
        super().handle_error(request, client_address)  # type: ignore[misc]


class SafeHTTPServer(_HandleErrorMixin, http.server.HTTPServer):
    """Drop-in replacement for ``http.server.HTTPServer`` with quiet disconnects."""


class SafeThreadingHTTPServer(_HandleErrorMixin, http.server.ThreadingHTTPServer):
    """Drop-in replacement for ``http.server.ThreadingHTTPServer`` with quiet disconnects."""
