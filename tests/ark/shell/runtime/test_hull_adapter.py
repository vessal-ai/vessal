"""test_hull_adapter.py — unit tests for HullHttpHandlerBase."""
from __future__ import annotations

import io
from unittest.mock import MagicMock

from vessal.ark.shell.runtime.hull_adapter import HullHttpHandlerBase


def _make_handler(method: str, path: str, body: bytes = b"") -> tuple[HullHttpHandlerBase, MagicMock]:
    hull = MagicMock()
    hull.handle.return_value = (200, {"ok": True})

    class _FakeServer:
        pass

    server = _FakeServer()
    server.hull = hull

    handler = HullHttpHandlerBase.__new__(HullHttpHandlerBase)
    handler.server = server
    handler.path = path
    handler.command = method
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    handler.headers = {"Content-Length": str(len(body))}
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    return handler, hull


def test_get_routes_to_hull_handle_with_no_body() -> None:
    h, hull = _make_handler("GET", "/status")
    h.do_GET()
    hull.handle.assert_called_once_with("GET", "/status", None)


def test_get_routes_to_hull_handle_with_query_params() -> None:
    h, hull = _make_handler("GET", "/frames?after=42")
    h.do_GET()
    hull.handle.assert_called_once_with("GET", "/frames", {"after": 42})


def test_post_reads_json_body() -> None:
    h, hull = _make_handler("POST", "/wake", body=b'{"reason":"user_message"}')
    h.do_POST()
    hull.handle.assert_called_once_with("POST", "/wake", {"reason": "user_message"})


def test_post_with_empty_body_is_none() -> None:
    h, hull = _make_handler("POST", "/stop", body=b"")
    h.do_POST()
    hull.handle.assert_called_once_with("POST", "/stop", None)
