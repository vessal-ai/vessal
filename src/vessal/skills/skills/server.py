"""skills Skill HTTP routes.

Serves a management UI and proxies skill-list queries to Hull's /skills/list.
"""
from pathlib import Path

_hull_api = None
_static_cache: dict = {}


def _make_static_handler(filename: str):
    def handler(_body):
        cached = _static_cache.get(filename)
        if cached is not None:
            return 200, cached
        return 404, {"error": f"{filename} not found"}
    return handler


def start(hull_api, skill=None) -> None:
    global _hull_api
    _hull_api = hull_api

    ui_dir = Path(__file__).parent / "ui"
    from vessal.ark.shell.hull.hull_api import StaticResponse

    for name in ("index.html", "app.js", "style.css"):
        path = ui_dir / name
        if path.exists():
            _static_cache[name] = StaticResponse.from_file(path)
        hull_api.register_route("GET", f"/ui/{name}", _make_static_handler(name))


def stop() -> None:
    global _hull_api
    if _hull_api is not None:
        for name in ("index.html", "app.js", "style.css"):
            _hull_api.unregister_route(f"/ui/{name}")
        _static_cache.clear()
        _hull_api = None
