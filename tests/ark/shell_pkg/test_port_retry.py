"""Tests for ShellServer port auto-retry on bind conflict."""
import socket
import threading

from vessal.ark.shell.server import ShellServer


def _occupy_port(port: int) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    s.bind(("127.0.0.1", port))
    s.listen(1)
    return s


def test_default_bind_is_localhost():
    server = ShellServer(project_dir="/tmp", port=0)
    assert server._host == "127.0.0.1"


def test_port_retries_on_conflict(monkeypatch, tmp_path):
    (tmp_path / "hull.toml").write_text("[agent]\nname = 'test'\n")
    base = 48420
    occupied = _occupy_port(base)
    try:
        server = ShellServer(project_dir=str(tmp_path), port=base)
        monkeypatch.setattr(server, "_spawn_hull", lambda: setattr(server, "_internal_port", 9999))
        monkeypatch.setattr(server, "_monitor_hull", lambda: None)
        server.start()
        try:
            assert server.port != base
            assert server.port == base + 1 or server.port > base
        finally:
            server.shutdown()
    finally:
        occupied.close()
