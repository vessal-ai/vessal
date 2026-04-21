"""test_server_routes — skills/server.py mounts static UI assets and nothing else."""
from __future__ import annotations

from vessal.ark.shell.hull.hull_api import HullApi, ScopedHullApi
from vessal.skills.skills import server as skills_server


def test_start_mounts_only_ui_routes():
    routes: dict = {}
    hull_api = HullApi(routes=routes, wake_fn=lambda _r: None)
    scoped = ScopedHullApi(hull_api, "skills")

    skills_server.start(scoped, skill=None)
    try:
        assert ("GET", "/skills/skills/ui/index.html") in routes
        assert ("GET", "/skills/skills/ui/app.js") in routes
        assert ("GET", "/skills/skills/ui/style.css") in routes
        # skills/server.py must NOT own /skills/list — that's Hull's.
        assert ("GET", "/skills/list") not in routes
    finally:
        skills_server.stop()


def test_stop_clears_routes():
    routes: dict = {}
    hull_api = HullApi(routes=routes, wake_fn=lambda _r: None)
    scoped = ScopedHullApi(hull_api, "skills")
    skills_server.start(scoped, skill=None)
    skills_server.stop()
    assert routes == {}
