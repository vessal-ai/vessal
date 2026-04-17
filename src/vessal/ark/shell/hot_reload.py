"""hot_reload.py — file watcher + dispatcher for Vessal's tiered hot reload.

Tier 1: SOUL.md changed → POST /reload/soul to Hull.
Tier 2: skills/<name>/**/*.py changed → POST /reload/skill with {"name": "<name>"}.
Tier 3: hull.toml changed → publish {"type": "restart_required"} to EventBus.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


def classify_change(path: str, project_dir: Path) -> tuple[str, str | None] | None:
    """Classify a changed file path into a hot-reload category.

    Returns:
        - ("soul", None) for SOUL.md
        - ("skill", <name>) for skills/<name>/**/*.py
        - ("hull_toml", None) for hull.toml
        - None if the path is irrelevant.
    """
    p = Path(path).resolve()
    project = project_dir.resolve()
    try:
        rel = p.relative_to(project)
    except ValueError:
        return None

    parts = rel.parts
    if rel.name == "SOUL.md":
        return ("soul", None)
    if rel.name == "hull.toml" and len(parts) == 1:
        return ("hull_toml", None)
    if len(parts) >= 3 and parts[0] == "skills" and rel.suffix == ".py":
        return ("skill", parts[1])
    return None


class HotReloader:
    def __init__(
        self,
        project_dir: Path,
        internal_port_getter: Callable[[], int | None],
        publish: Callable[[dict], None],
    ) -> None:
        self._project_dir = project_dir
        self._get_port = internal_port_getter
        self._publish = publish
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="hot-reload")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            from watchfiles import watch
        except ImportError:
            logger.warning("watchfiles not installed; hot reload disabled")
            return
        for changes in watch(str(self._project_dir), stop_event=self._stop):
            for _change_type, path in changes:
                decision = classify_change(path, self._project_dir)
                if decision is None:
                    continue
                kind, name = decision
                try:
                    self._dispatch(kind, name)
                except Exception as e:
                    logger.warning("hot_reload dispatch failed (%s %s): %s", kind, name, e)

    def _dispatch(self, kind: str, name: str | None) -> None:
        port = self._get_port()
        if port is None:
            return
        if kind == "soul":
            self._post(port, "/reload/soul", {})
        elif kind == "skill" and name:
            self._post(port, "/reload/skill", {"name": name})
        elif kind == "hull_toml":
            self._publish({"type": "restart_required", "ts": time.time(), "payload": {"file": "hull.toml"}})

    def _post(self, port: int, path: str, body: dict) -> None:
        url = f"http://127.0.0.1:{port}{path}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            urllib.request.urlopen(req, timeout=3).read()
        except urllib.error.URLError as e:
            logger.warning("hot_reload POST %s failed: %s", path, e)
