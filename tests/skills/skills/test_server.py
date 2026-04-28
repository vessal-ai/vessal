from unittest.mock import MagicMock
from vessal.skills.skills import server as skills_server


def test_start_registers_ui_routes():
    api = MagicMock()
    skills_server.start(api)
    registered = {(c.args[0], c.args[1]) for c in api.register_route.call_args_list}
    for path in ("/ui/index.html", "/ui/app.js", "/ui/style.css"):
        assert ("GET", path) in registered
    skills_server.stop()
