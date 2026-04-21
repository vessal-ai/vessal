"""test_server_routes — chat/server.py start() mounts expected UI routes."""
from __future__ import annotations

from vessal.ark.shell.hull.hull_api import HullApi, ScopedHullApi
from vessal.skills.chat import server as chat_server


def test_start_registers_static_and_api_routes():
    routes: dict = {}
    hull_api = HullApi(routes=routes, wake_fn=lambda _r: None)
    scoped = ScopedHullApi(hull_api, "chat")

    chat_server.start(scoped, skill=None)
    try:
        assert ("GET", "/skills/chat/ui/index.html") in routes
        assert ("GET", "/skills/chat/ui/app.js") in routes
        assert ("GET", "/skills/chat/ui/style.css") in routes
        assert ("GET", "/skills/chat/ui/render.js") in routes
        assert ("POST", "/skills/chat/inbox") in routes
        assert ("GET", "/skills/chat/outbox") in routes
        assert ("GET", "/skills/chat/history") in routes
    finally:
        chat_server.stop()


def test_stop_unregisters_all_routes():
    routes: dict = {}
    hull_api = HullApi(routes=routes, wake_fn=lambda _r: None)
    scoped = ScopedHullApi(hull_api, "chat")

    chat_server.start(scoped, skill=None)
    chat_server.stop()
    assert routes == {}
