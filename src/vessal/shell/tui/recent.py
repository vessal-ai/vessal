"""recent.py — ~/.vessal/recent.json for TUI 'Open recent' submenu."""
from __future__ import annotations

import json
import os
from pathlib import Path

_MAX = 20


class RecentProjects:
    def __init__(self) -> None:
        self._path = Path(os.path.expanduser("~")) / ".vessal" / "recent.json"

    def _load(self) -> list[str]:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text(encoding="utf-8")).get("projects", [])
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, items: list[str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"projects": items}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, project_dir: str) -> None:
        absolute = str(Path(project_dir).resolve())
        items = [p for p in self._load() if p != absolute]
        items.insert(0, absolute)
        del items[_MAX:]
        self._save(items)

    def list(self) -> list[str]:
        return list(self._load())
