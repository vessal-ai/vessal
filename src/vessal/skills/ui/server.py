"""ui Skill HTTP routes.

Hull-managed mode: start(hull_api, skill) registers routes.
GET /         → index.html
GET /render   → latest render spec (polling)
POST /events  → receives user events
"""
from __future__ import annotations

from pathlib import Path


_hull_api = None
_skill = None
_static_cache: dict = {}
_last_spec: dict | None = None
_last_version: int = -1


def _make_static_handler(filename: str):
    def handler(_body):
        cached = _static_cache.get(filename)
        if cached is not None:
            return 200, cached
        return 404, {"error": f"{filename} not found"}
    return handler


def start(hull_api, skill=None) -> None:
    """Hull-managed entry point."""
    global _hull_api, _skill

    _hull_api = hull_api
    _skill = skill

    # Load index.html
    static_dir = Path(__file__).parent / "static"
    index_path = static_dir / "index.html"

    from vessal.ark.shell.hull.hull_api import StaticResponse

    if index_path.exists():
        _static_cache["index.html"] = StaticResponse(
            index_path.read_bytes(), "text/html; charset=utf-8"
        )

    # Load static assets
    for fname in ("renderer.js", "avatar.js", "avatar.css", "style.css", "poll.js"):
        fpath = static_dir / fname
        if fpath.exists():
            _static_cache[fname] = StaticResponse.from_file(fpath)
            hull_api.register_route("GET", f"/{fname}", _make_static_handler(fname))

    hull_api.register_route("GET", "/", _handle_index)
    hull_api.register_route("GET", "/render", _handle_render)
    hull_api.register_route("POST", "/events", _handle_events)


def stop() -> None:
    """Hull-managed shutdown."""
    global _hull_api, _skill, _last_spec, _last_version
    if _hull_api is not None:
        _hull_api.unregister_route("/")
        _hull_api.unregister_route("/render")
        _hull_api.unregister_route("/events")
        # unregister_route is idempotent — safe even if file didn't exist at start() time
        for fname in ("renderer.js", "avatar.js", "avatar.css", "style.css", "poll.js"):
            _hull_api.unregister_route(f"/{fname}")
        _static_cache.clear()
        _hull_api = None
        _skill = None
        _last_spec = None
        _last_version = -1


def _handle_index(_body):
    """GET / — UI page."""
    cached = _static_cache.get("index.html")
    if cached is not None:
        return 200, cached
    return 404, {"error": "index.html not found"}


def _handle_render(body):
    """GET /render — return the latest render spec. Supports conditional polling."""
    global _last_spec, _last_version

    # Consume the latest spec from skill outbox
    if _skill is not None:
        specs = _skill.drain_outbox()
        if specs:
            _last_spec = specs[-1]  # keep only the latest
            _last_version = _last_spec.get("version", _last_version)

    # Return empty spec if nothing has been rendered yet
    if _last_spec is None:
        return 200, {"version": -1, "body": {}, "components": [], "interactions": []}

    # Conditional return: only check version when client explicitly provides after_version
    body = body or {}
    if "after_version" in body:
        try:
            client_version = int(body["after_version"])
        except (TypeError, ValueError):
            client_version = -1
        if client_version >= _last_version:
            return 200, {"unchanged": True, "version": _last_version}

    return 200, _last_spec


def _handle_events(body):
    """POST /events — receive user events."""
    body = body or {}

    if _skill is not None:
        _skill.receive_event(body)

    if _hull_api is not None:
        _hull_api.wake("ui_event")

    return 200, {"status": "ok"}
