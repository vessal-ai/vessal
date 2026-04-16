"""test_server — Shell HTTP endpoint tests (forwarded to fake backend via _ProxyHandler)."""
import http.server
import json
import threading
import urllib.request
import urllib.error

import pytest

from vessal.ark.shell.server import ShellServer


class _FakeHullBackend(http.server.BaseHTTPRequestHandler):
    """Simulated Hull subprocess HTTP backend, returns preset responses directly."""

    # Class-level response dict, tests can modify
    responses: dict = {}

    def do_GET(self):
        path = self.path.split("?")[0]
        status, data = self.responses.get(path, (200, {}))
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)  # consume body
        status, data = self.responses.get(path, (200, {}))
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


@pytest.fixture
def shell_server(monkeypatch, tmp_path):
    """Create and start ShellServer; _spawn_hull is monkeypatched to avoid a real subprocess."""
    # Start fake Hull HTTP backend
    backend = http.server.HTTPServer(("127.0.0.1", 0), _FakeHullBackend)
    backend_port = backend.server_address[1]
    t = threading.Thread(target=backend.serve_forever, daemon=True)
    t.start()

    # Default responses
    _FakeHullBackend.responses = {
        "/status": (200, {"idle": False, "frame": 5, "wake": "user_message"}),
        "/wake": (200, {"status": "accepted"}),
        "/frames": (200, {"frames": [{"number": 1}, {"number": 2}]}),
        "/stop": (200, {"status": "stopping"}),
    }

    def fake_spawn(self):
        self._internal_port = backend_port
        self._hull_alive = True

    monkeypatch.setattr(
        "vessal.ark.shell.server.ShellServer._spawn_hull", fake_spawn
    )

    server = ShellServer(project_dir=str(tmp_path), port=0)
    server.start()
    port = server._http_server.server_address[1]

    yield server, port

    server.shutdown()
    backend.shutdown()


class TestStatusEndpoint:
    def test_get_status(self, shell_server):
        server, port = shell_server
        url = f"http://127.0.0.1:{port}/status"
        with urllib.request.urlopen(url, timeout=2) as resp:
            data = json.loads(resp.read())
        assert data["idle"] is False
        assert data["frame"] == 5


class TestWakeEndpoint:
    def test_post_wake(self, shell_server):
        server, port = shell_server
        url = f"http://127.0.0.1:{port}/wake"
        body = json.dumps({"reason": "user_message"}).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
        assert data["status"] == "accepted"


class TestFramesEndpoint:
    def test_get_frames(self, shell_server):
        server, port = shell_server
        url = f"http://127.0.0.1:{port}/frames"
        with urllib.request.urlopen(url, timeout=2) as resp:
            data = json.loads(resp.read())
        assert len(data["frames"]) == 2

    def test_get_frames_with_after(self, shell_server, monkeypatch):
        server, port = shell_server
        _FakeHullBackend.responses["/frames"] = (200, {"frames": [{"number": 2}]})
        url = f"http://127.0.0.1:{port}/frames?after=1"
        with urllib.request.urlopen(url, timeout=2) as resp:
            data = json.loads(resp.read())
        assert len(data["frames"]) == 1


class TestStopEndpoint:
    def test_post_stop(self, shell_server):
        server, port = shell_server
        url = f"http://127.0.0.1:{port}/stop"
        req = urllib.request.Request(url, data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
        assert data["status"] == "stopping"
