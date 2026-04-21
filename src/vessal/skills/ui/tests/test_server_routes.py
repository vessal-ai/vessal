"""test_server_routes — ui/server.py start() mounts expected routes, stop() is clean."""
from __future__ import annotations

from vessal.ark.shell.hull.hull_api import HullApi, ScopedHullApi
from vessal.skills.ui import server as ui_server


EXPECTED_ROUTES = {
    ("GET", "/skills/ui/"),
    ("GET", "/skills/ui/render"),
    ("POST", "/skills/ui/events"),
    ("GET", "/skills/ui/ui/renderer.js"),
    ("GET", "/skills/ui/ui/avatar.js"),
    ("GET", "/skills/ui/ui/avatar.css"),
    ("GET", "/skills/ui/ui/style.css"),
    ("GET", "/skills/ui/ui/poll.js"),
}


def test_start_mounts_expected_routes():
    routes: dict = {}
    hull_api = HullApi(routes=routes, wake_fn=lambda _r: None)
    scoped = ScopedHullApi(hull_api, "ui")

    ui_server.start(scoped, skill=None)
    try:
        missing = EXPECTED_ROUTES - set(routes)
        assert not missing, f"missing routes: {missing}"
    finally:
        ui_server.stop()


def test_stop_clears_all_routes():
    routes: dict = {}
    hull_api = HullApi(routes=routes, wake_fn=lambda _r: None)
    scoped = ScopedHullApi(hull_api, "ui")
    ui_server.start(scoped, skill=None)
    ui_server.stop()
    assert routes == {}
