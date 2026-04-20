"""test_container_mode.py — ContainerHullHandler HTTP handler tests."""
import http.server
import json
import threading
import urllib.request

import pytest


class FakeHull:
    """Minimal Hull stub that records calls to handle()."""

    def __init__(self, response=(200, {"ok": True})):
        self._response = response
        self.calls = []

    def handle(self, method, path, body):
        self.calls.append((method, path, body))
        return self._response

    def status(self):
        return {"sleeping": True}

    def stop(self):
        self._stopped = True

    async def run(self):
        pass


def _start_server(handler_cls, hull):
    """Start HTTP server on random port, return (server, port)."""
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    server.hull = hull
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, port


class TestContainerHullHandler:
    """ContainerHullHandler forwards HTTP to hull.handle()."""

    def test_get_forwards_to_handle(self):
        from vessal.ark.shell.runtime.container_mode import ContainerHullHandler

        hull = FakeHull(response=(200, {"status": "ok"}))
        server, port = _start_server(ContainerHullHandler, hull)
        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/status")
            data = json.loads(resp.read())
            assert data == {"status": "ok"}
            assert hull.calls == [("GET", "/status", None)]
        finally:
            server.shutdown()

    def test_post_forwards_json_body(self):
        from vessal.ark.shell.runtime.container_mode import ContainerHullHandler

        hull = FakeHull(response=(200, {"received": True}))
        server, port = _start_server(ContainerHullHandler, hull)
        try:
            payload = json.dumps({"msg": "hello"}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/wake",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req)
            data = json.loads(resp.read())
            assert data == {"received": True}
            assert hull.calls[0][0] == "POST"
            assert hull.calls[0][1] == "/wake"
            assert hull.calls[0][2] == {"msg": "hello"}
        finally:
            server.shutdown()

    def test_healthz_does_not_hit_hull(self):
        from vessal.ark.shell.runtime.container_mode import ContainerHullHandler

        hull = FakeHull()
        server, port = _start_server(ContainerHullHandler, hull)
        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz")
            data = json.loads(resp.read())
            assert data["status"] == "ok"
            assert hull.calls == []  # /healthz does NOT go through Hull
        finally:
            server.shutdown()

    def test_static_response(self):
        from vessal.ark.shell.hull.hull_api import StaticResponse
        from vessal.ark.shell.runtime.container_mode import ContainerHullHandler

        hull = FakeHull(response=(200, StaticResponse(b"<h1>hi</h1>", "text/html")))
        server, port = _start_server(ContainerHullHandler, hull)
        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/page")
            assert resp.headers["Content-Type"] == "text/html"
            assert b"<h1>hi</h1>" in resp.read()
        finally:
            server.shutdown()

    def test_get_with_query_params(self):
        from vessal.ark.shell.runtime.container_mode import ContainerHullHandler

        hull = FakeHull(response=(200, {"frames": []}))
        server, port = _start_server(ContainerHullHandler, hull)
        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/frames?after=5")
            json.loads(resp.read())
            _, path, body = hull.calls[0]
            assert path == "/frames"
            assert body == {"after": 5}
        finally:
            server.shutdown()

    def test_post_empty_body(self):
        from vessal.ark.shell.runtime.container_mode import ContainerHullHandler

        hull = FakeHull(response=(200, {"ok": True}))
        server, port = _start_server(ContainerHullHandler, hull)
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/stop",
                data=b"",
                method="POST",
            )
            resp = urllib.request.urlopen(req)
            assert hull.calls[0][2] is None
        finally:
            server.shutdown()
