"""test_server_static — chat server static file route tests."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock


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


def test_static_handler_returns_css(tmp_path, monkeypatch):
    """Static file handler returns correct content_type."""
    from vessal.skills.chat import server as chat_server
    # Create a temporary css file in tmp_path, monkeypatch the static cache
    css_file = tmp_path / "style.css"
    css_file.write_text("body { color: red; }", encoding="utf-8")
    from vessal.ark.shell.hull.hull_api import StaticResponse
    monkeypatch.setitem(chat_server._static_cache, "style.css", StaticResponse.from_file(css_file))
    handler = chat_server._make_static_handler("style.css")
    status, resp = handler(None)
    assert status == 200
    assert "text/css" in resp.content_type
