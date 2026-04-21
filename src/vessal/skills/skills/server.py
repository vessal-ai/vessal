"""skills Skill HTTP routes — mounts the Console inventory UI.

Registers static routes under /skills/skills/ui/<file>. The UI's app.js fetches skill data
from Hull's /skills/list directly; this server does not proxy data calls.
"""
from __future__ import annotations

from pathlib import Path

from vessal.ark.shell.hull.skill_static import StaticRouter


_static: StaticRouter | None = None


def start(hull_api, skill=None) -> None:
    global _static
    ui_dir = Path(__file__).parent / "ui"
    _static = StaticRouter(hull_api, ui_dir)
    _static.register(["index.html", "app.js", "style.css"])


def stop() -> None:
    global _static
    if _static is not None:
        _static.unregister()
        _static = None
