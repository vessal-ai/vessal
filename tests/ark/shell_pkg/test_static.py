"""Tests for /console/* static serving in ShellServer."""
import urllib.request


def test_console_root_redirects_to_index(monkeypatch, tmp_path):
    (tmp_path / "hull.toml").write_text("[agent]\nname='x'\n")
    from vessal.ark.shell.server import ShellServer
    server = ShellServer(project_dir=str(tmp_path), port=0)
    monkeypatch.setattr(server, "_spawn_hull", lambda: setattr(server, "_internal_port", 9999))
    monkeypatch.setattr(server, "_monitor_hull", lambda: None)
    server.start()
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{server.port}/console/", timeout=2)
        body = resp.read().decode()
        assert resp.status == 200
        assert "<!doctype html>" in body.lower()
        assert 'id="app"' in body
    finally:
        server.shutdown()


def test_console_asset_served(monkeypatch, tmp_path):
    (tmp_path / "hull.toml").write_text("[agent]\nname='x'\n")
    from vessal.ark.shell.server import ShellServer
    server = ShellServer(project_dir=str(tmp_path), port=0)
    monkeypatch.setattr(server, "_spawn_hull", lambda: setattr(server, "_internal_port", 9999))
    monkeypatch.setattr(server, "_monitor_hull", lambda: None)
    server.start()
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{server.port}/console/assets/style.css", timeout=2)
        assert resp.status == 200
        assert "text/css" in resp.headers.get("Content-Type", "")
    finally:
        server.shutdown()
