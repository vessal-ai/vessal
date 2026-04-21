"""test_skill_static — StaticRouter registers, serves, and unregisters static assets cleanly."""
from __future__ import annotations

from pathlib import Path

import pytest

from vessal.ark.shell.hull.hull_api import HullApi, ScopedHullApi, StaticResponse
from vessal.ark.shell.hull.skill_static import StaticRouter


@pytest.fixture
def scoped_api(tmp_path):
    routes: dict = {}
    hull_api = HullApi(routes=routes, wake_fn=lambda _r: None)
    return ScopedHullApi(hull_api, "demo"), routes


def _write_asset(dir_: Path, name: str, content: bytes = b"x") -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    path = dir_ / name
    path.write_bytes(content)
    return path


def test_registers_all_present_files_under_ui_prefix(scoped_api, tmp_path):
    scoped, routes = scoped_api
    ui_dir = tmp_path / "ui"
    _write_asset(ui_dir, "index.html", b"<html></html>")
    _write_asset(ui_dir, "app.js", b"console.log(1)")

    router = StaticRouter(scoped, ui_dir)
    router.register(["index.html", "app.js", "missing.css"])

    assert ("GET", "/skills/demo/ui/index.html") in routes
    assert ("GET", "/skills/demo/ui/app.js") in routes
    assert ("GET", "/skills/demo/ui/missing.css") not in routes


def test_handler_returns_cached_static_response(scoped_api, tmp_path):
    scoped, routes = scoped_api
    ui_dir = tmp_path / "ui"
    _write_asset(ui_dir, "index.html", b"<html>hello</html>")

    router = StaticRouter(scoped, ui_dir)
    router.register(["index.html"])

    handler = routes[("GET", "/skills/demo/ui/index.html")]
    status, body = handler(None)
    assert status == 200
    assert isinstance(body, StaticResponse)
    assert body.content == b"<html>hello</html>"
    assert "text/html" in body.content_type


def test_unregister_removes_all_registered_routes(scoped_api, tmp_path):
    scoped, routes = scoped_api
    ui_dir = tmp_path / "ui"
    _write_asset(ui_dir, "index.html")
    _write_asset(ui_dir, "style.css")

    router = StaticRouter(scoped, ui_dir)
    router.register(["index.html", "style.css"])
    assert len(routes) == 2

    router.unregister()
    assert routes == {}


def test_unregister_is_idempotent(scoped_api, tmp_path):
    scoped, routes = scoped_api
    ui_dir = tmp_path / "ui"
    _write_asset(ui_dir, "index.html")

    router = StaticRouter(scoped, ui_dir)
    router.register(["index.html"])
    router.unregister()
    router.unregister()  # must not raise


def test_register_raises_if_already_active(scoped_api, tmp_path):
    scoped, _ = scoped_api
    ui_dir = tmp_path / "ui"
    _write_asset(ui_dir, "index.html")

    router = StaticRouter(scoped, ui_dir)
    router.register(["index.html"])
    with pytest.raises(RuntimeError, match="already registered"):
        router.register(["index.html"])


def test_register_empty_list_is_noop(scoped_api, tmp_path):
    scoped, routes = scoped_api
    router = StaticRouter(scoped, tmp_path)
    router.register([])
    assert routes == {}
