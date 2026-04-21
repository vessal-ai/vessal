"""skill_static.py — StaticRouter: mount a Skill's UI static assets under /ui/<file>.

Replaces the boilerplate module-global state (_hull_api, _static_cache, _make_static_handler)
that otherwise gets copy-pasted into every Skill's server.py. Single source of truth for how
Skill UIs expose static files.

Route shape: every asset mounts at `{scoped_api._prefix}/ui/<filename>` — e.g. a skill named
`chat` publishing `index.html` ends up at `/skills/chat/ui/index.html`.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from vessal.ark.shell.hull.hull_api import StaticResponse

if TYPE_CHECKING:
    from vessal.ark.shell.hull.hull_api import ScopedHullApi


class StaticRouter:
    """Registers a fixed set of static files beneath `/ui/` on a ScopedHullApi.

    Non-existent filenames are silently skipped at register time — this mirrors the
    defensive behavior of the old boilerplate (where a missing file simply produced no
    route) and keeps Skills tolerant of partial UI bundles during development.
    """

    _UI_PREFIX = "/ui/"

    def __init__(self, hull_api: "ScopedHullApi", ui_dir: Path) -> None:
        self._hull_api = hull_api
        self._ui_dir = Path(ui_dir)
        self._registered_paths: list[str] = []
        self._cache: dict[str, StaticResponse] = {}

    def register(self, filenames: list[str]) -> None:
        """Cache file bytes and mount a GET handler for each filename that exists on disk."""
        if self._registered_paths:
            raise RuntimeError(
                f"StaticRouter for {self._ui_dir} is already registered; call unregister() first"
            )
        for name in filenames:
            path = self._ui_dir / name
            if not path.exists():
                continue
            self._cache[name] = StaticResponse.from_file(path)
            route_path = f"{self._UI_PREFIX}{name}"
            self._hull_api.register_route("GET", route_path, self._make_handler(name))
            self._registered_paths.append(route_path)

    def unregister(self) -> None:
        """Unregister every previously-mounted path and drop the byte cache."""
        for route_path in self._registered_paths:
            self._hull_api.unregister_route(route_path)
        self._registered_paths.clear()
        self._cache.clear()

    def _make_handler(self, filename: str):
        def handler(_body):
            cached = self._cache.get(filename)
            if cached is None:
                return 404, {"error": f"{filename} not found"}
            return 200, cached
        return handler
