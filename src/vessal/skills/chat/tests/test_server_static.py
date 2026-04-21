"""test_server_static — chat server static file route tests."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_hull_api():
    api = MagicMock()
    api.register_route = MagicMock()
    return api


def test_start_registers_static_routes(mock_hull_api):
    """start() registers style.css / app.js / render.js routes under /ui/."""
    from vessal.skills.chat.server import start
    start(mock_hull_api)
    registered_paths = [call[0][1] for call in mock_hull_api.register_route.call_args_list]
    assert "/ui/style.css" in registered_paths
    assert "/ui/app.js" in registered_paths
    assert "/ui/render.js" in registered_paths


def test_static_handler_returns_css(tmp_path):
    """StaticRouter serves correct content_type for CSS files."""
    from vessal.ark.shell.hull.skill_static import StaticRouter

    css_file = tmp_path / "style.css"
    css_file.write_text("body { color: red; }", encoding="utf-8")

    routes: dict = {}
    from vessal.ark.shell.hull.hull_api import HullApi, ScopedHullApi
    hull_api = HullApi(routes=routes, wake_fn=lambda _r: None)
    scoped = ScopedHullApi(hull_api, "chat")

    router = StaticRouter(scoped, tmp_path)
    router.register(["style.css"])

    handler = routes[("GET", "/skills/chat/ui/style.css")]
    status, resp = handler(None)
    assert status == 200
    assert "text/css" in resp.content_type
