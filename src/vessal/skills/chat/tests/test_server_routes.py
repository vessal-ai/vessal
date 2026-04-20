"""Verify chat skill registers UI routes under /ui/* and no longer at root."""
from pathlib import Path
from unittest.mock import MagicMock

from vessal.skills.chat import server as chat_server


def test_start_registers_ui_routes():
    api = MagicMock()
    skill = MagicMock()
    skill._data_dir = Path("/tmp")

    chat_server.start(api, skill)

    registered = {(call.args[0], call.args[1]) for call in api.register_route.call_args_list}
    assert ("GET", "/ui/index.html") in registered
    assert ("GET", "/ui/app.js") in registered
    assert ("GET", "/ui/style.css") in registered
    assert ("GET", "/ui/render.js") in registered
    assert ("POST", "/inbox") in registered
    assert ("GET", "/outbox") in registered

    # The root path must NOT be registered — discovery points directly to /ui/index.html
    assert ("GET", "/") not in registered

    chat_server.stop()
