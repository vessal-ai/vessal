"""test_server_routes — skill_manager/server.py mounts static UI assets and nothing else."""
from __future__ import annotations

from vessal.hull.hull_api import HullApi, ScopedHullApi
from vessal.skills.skill_manager import server as skill_manager_server


def test_start_mounts_only_ui_routes():
    routes: dict = {}
    hull_api = HullApi(routes=routes, wake_fn=lambda _r: None)
    scoped = ScopedHullApi(hull_api, "skill_manager")

    skill_manager_server.start(scoped, skill=None)
    try:
        assert ("GET", "/skills/skill_manager/ui/index.html") in routes
        assert ("GET", "/skills/skill_manager/ui/app.js") in routes
        assert ("GET", "/skills/skill_manager/ui/style.css") in routes
        # skill_manager/server.py must NOT own /skills/list — that's Hull's.
        assert ("GET", "/skills/list") not in routes
    finally:
        skill_manager_server.stop()


def test_stop_clears_routes():
    routes: dict = {}
    hull_api = HullApi(routes=routes, wake_fn=lambda _r: None)
    scoped = ScopedHullApi(hull_api, "skill_manager")
    skill_manager_server.start(scoped, skill=None)
    skill_manager_server.stop()
    assert routes == {}
