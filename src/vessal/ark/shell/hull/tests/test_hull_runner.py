"""test_hull_runner.py — Unit tests for the Hull subprocess entry module."""
import http.server
import json
import threading
import urllib.request

import pytest


def test_hull_handler_forwards_get():
    """_HullHandler forwards GET requests to hull.handle()."""
    from vessal.ark.shell.hull_runner import _HullHandler

    class FakeHull:
        def handle(self, method, path, body):
            return 200, {"method": method, "path": path}

    server = http.server.HTTPServer(("127.0.0.1", 0), _HullHandler)
    server.hull = FakeHull()
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/status")
        data = json.loads(resp.read())
        assert data["method"] == "GET"
        assert data["path"] == "/status"
    finally:
        server.shutdown()


def test_hull_handler_forwards_post():
    """_HullHandler forwards POST requests to hull.handle()."""
    from vessal.ark.shell.hull_runner import _HullHandler

    class FakeHull:
        def handle(self, method, path, body):
            return 200, {"received": body}

    server = http.server.HTTPServer(("127.0.0.1", 0), _HullHandler)
    server.hull = FakeHull()
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        payload = json.dumps({"msg": "hello"}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/inbox",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        assert data["received"] == {"msg": "hello"}
    finally:
        server.shutdown()


def test_hull_handler_static_response():
    """_HullHandler correctly handles StaticResponse return values."""
    from vessal.ark.shell.hull.hull_api import StaticResponse
    from vessal.ark.shell.hull_runner import _HullHandler

    class FakeHull:
        def handle(self, method, path, body):
            return 200, StaticResponse(b"<h1>hi</h1>", "text/html")

    server = http.server.HTTPServer(("127.0.0.1", 0), _HullHandler)
    server.hull = FakeHull()
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/page")
        assert resp.headers["Content-Type"] == "text/html"
        assert b"<h1>hi</h1>" in resp.read()
    finally:
        server.shutdown()
