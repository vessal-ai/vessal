"""test_proxy.py — Unit tests for the Shell reverse proxy."""
import http.server
import json
import threading
import urllib.request
import urllib.error

import pytest


class _FakeBackend(http.server.BaseHTTPRequestHandler):
    """Simulated Hull subprocess HTTP backend."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        body = json.dumps({"from": "backend", "path": self.path}).encode()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        req_body = self.rfile.read(length) if length else b""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        body = json.dumps({"from": "backend", "posted": req_body.decode()}).encode()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


@pytest.fixture
def backend_port():
    """Start a fake backend and return its port number."""
    server = http.server.HTTPServer(("127.0.0.1", 0), _FakeBackend)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield port
    server.shutdown()


def test_proxy_forwards_get(backend_port):
    """_ProxyHandler forwards GET to backend and returns the response."""
    from vessal.ark.shell.server import _ProxyHandler

    server = http.server.HTTPServer(("127.0.0.1", 0), _ProxyHandler)
    server.internal_port = backend_port
    server.hull_alive = True
    proxy_port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{proxy_port}/status")
        data = json.loads(resp.read())
        assert data["from"] == "backend"
        assert data["path"] == "/status"
    finally:
        server.shutdown()


def test_proxy_forwards_post(backend_port):
    """_ProxyHandler forwards POST body to backend."""
    from vessal.ark.shell.server import _ProxyHandler

    server = http.server.HTTPServer(("127.0.0.1", 0), _ProxyHandler)
    server.internal_port = backend_port
    server.hull_alive = True
    proxy_port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        payload = json.dumps({"msg": "hello"}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{proxy_port}/inbox",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        assert data["from"] == "backend"
    finally:
        server.shutdown()


def test_proxy_returns_503_when_hull_down():
    """_ProxyHandler returns 503 when Hull is unavailable."""
    from vessal.ark.shell.server import _ProxyHandler

    server = http.server.HTTPServer(("127.0.0.1", 0), _ProxyHandler)
    server.internal_port = 1  # non-existent port
    server.hull_alive = False
    proxy_port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{proxy_port}/status")
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 503
    finally:
        server.shutdown()


def test_proxy_forwards_error_status(backend_port):
    """_ProxyHandler forwards the real error status code from Hull (does not convert to 503)."""
    import http.server as _hs

    class _404Backend(_hs.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"error": "not found"}).encode()
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    err_server = _hs.HTTPServer(("127.0.0.1", 0), _404Backend)
    err_port = err_server.server_address[1]
    import threading as _t
    _t.Thread(target=err_server.serve_forever, daemon=True).start()

    from vessal.ark.shell.server import _ProxyHandler
    proxy = _hs.HTTPServer(("127.0.0.1", 0), _ProxyHandler)
    proxy.internal_port = err_port
    proxy.hull_alive = True
    proxy_port = proxy.server_address[1]
    _t.Thread(target=proxy.serve_forever, daemon=True).start()

    try:
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"http://127.0.0.1:{proxy_port}/missing")
        assert exc_info.value.code == 404
        data = json.loads(exc_info.value.read())
        assert data["error"] == "not found"
    finally:
        proxy.shutdown()
        err_server.shutdown()
