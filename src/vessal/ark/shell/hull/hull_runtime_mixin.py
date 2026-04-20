"""hull_runtime_mixin.py — Runtime-owned variables, event loop, and HTTP handle() for Hull.

Part of the Hull class via multiple-inheritance composition (see hull.py).
Methods here may assume the attributes set by Hull.__init__ (see `_HullAttrs` TYPE_CHECKING block).
"""
from __future__ import annotations

import logging
import queue
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from concurrent.futures import ThreadPoolExecutor

    from vessal.ark.shell.hull.cell import Cell
    from vessal.ark.shell.hull.cell.core import Core
    from vessal.ark.shell.hull.cell.kernel import RenderConfig
    from vessal.ark.shell.hull.cell.kernel.render.prompt import SystemPromptBuilder
    from vessal.ark.shell.hull.event_loop import EventLoop
    from vessal.ark.shell.hull.hull_api import HullApi
    from vessal.ark.shell.hull.skill_loader import SkillLoader
    from vessal.ark.util.logging import Tracer

logger = logging.getLogger(__name__)


class HullRuntimeMixin:
    """Runtime-owned variables, event loop lifecycle, and HTTP routing for Hull."""

    def wake(self, reason: str = "external", **metadata) -> None:
        """Wake the Agent. Shell uses this method to inject external events.

        Args:
            reason: Wake reason (e.g. "user_message", "heartbeat", "alarm", "webhook").
            **metadata: Additional info written into the event dict.
        """
        event = {"reason": reason, **metadata}
        self._event_loop.event_queue.put(event)

    def status(self) -> dict:
        """Query the current Agent status.

        Returns a snapshot dict; modifying the return value does not affect internal state.

        Returns:
            A dict with the following fields:
            - idle (bool): Whether the Agent is idle (same value as sleeping, kept for backward compat)
            - sleeping (bool): Whether the Agent is sleeping
            - frame (int): Current frame number
            - wake (str): Most recent wake reason
        """
        sleeping = self._cell.get("_sleeping", False)
        return {
            "idle": sleeping,
            "sleeping": sleeping,
            "frame": self._cell.get("_frame", 0),
            "wake": self._cell.get("_wake", ""),
        }

    def reload_soul(self) -> None:
        """Force re-read of SOUL.md regardless of mtime.

        Normal hot-reload is handled by _rewrite_runtime_owned's mtime check each
        frame. This method is called by the file watcher to invalidate the cache
        proactively (covers edge cases where two writes hit the same mtime tick).
        """
        if self._soul_path.exists():
            self._soul_text = self._soul_path.read_text(encoding="utf-8")
            self._soul_mtime = self._soul_path.stat().st_mtime

    def get_ns(self, key: str) -> Any:
        """Get a value from Cell namespace."""
        return self._cell.get(key)

    def set_ns(self, key: str, value: Any) -> None:
        """Set a value in Cell namespace."""
        self._cell.set(key, value)

    def ns_keys(self) -> list[str]:
        """Return all keys in Cell namespace."""
        return list(self._cell.keys())

    def frames(self, after: int | None = None) -> list[dict]:
        """Query hot-zone frames from the frame stream.

        Args:
            after: Only return frames with number > after. Returns all if None.

        Returns:
            A copy of all hot-zone frame dicts, ordered oldest to newest.
        """
        fs = self._cell.get("_frame_stream")
        if fs is None:
            return []
        # Flatten hot buckets oldest-first (B_4..B_0) into a single list
        all_frames: list[dict] = []
        for bucket in reversed(fs._hot):
            all_frames.extend(bucket)
        if after is not None:
            all_frames = [f for f in all_frames if f.get("number", 0) > after]
        return list(all_frames)

    def next_alarm(self) -> float | None:
        """Return the absolute timestamp of the Agent's next scheduled wake-up.

        The Agent sets an alarm via the _next_wake namespace variable.
        Shell uses this method to schedule the next wake.

        Returns:
            Alarm timestamp (float), or None if no alarm is set.
        """
        next_wake = self._cell.get("_next_wake")
        if isinstance(next_wake, (int, float)) and next_wake > 0:
            return float(next_wake)
        return None

    async def run(self) -> None:
        """Start the persistent event loop: wait for wake → frame loop → idle → wait again.

        Called by Shell inside an asyncio event loop. Runs continuously until stop() is called.
        """
        await self._event_loop.run_forever()

    async def run_once(self) -> None:
        """Execute a single wake cycle and return.

        Waits for one event, runs the frame loop until idle, then returns.
        Used for `vessal run --goal "..."` single-run mode.
        """
        await self._event_loop.run_once()

    def stop(self) -> None:
        """Request stop."""
        self._event_loop.stop()
        self._thread_pool.shutdown(wait=False)

    def handle(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict | "StaticResponse"]:
        """Single entry point for HTTP requests. Shell calls this; Hull routes internally.

        Args:
            method: HTTP method ("GET", "POST", etc.)
            path:   URL path ("/status", "/frames", etc.)
            body:   JSON body dict (or None for GET)

        Returns:
            (status_code, response). If response is a dict Shell returns JSON;
            if it is a StaticResponse Shell returns raw content with content_type.
        """
        body = body or {}
        method = method.upper()
        route_key = (method, path)

        # Dynamic routes (registered by skill servers)
        handler = self._routes.get(route_key)
        if handler is not None:
            try:
                return handler(body)
            except Exception as e:
                logger.warning("Route %s %s handler failed: %s", method, path, e)
                return 500, {"error": str(e)}

        # Built-in routes
        if method == "GET" and path == "/status":
            return 200, self.status()
        if method == "GET" and path.startswith("/frames"):
            after = None
            if "?" in path:
                from urllib.parse import parse_qs, urlparse
                qs = parse_qs(urlparse(path).query)
                if "after" in qs:
                    after = int(qs["after"][0])
            if after is None:
                after = (body or {}).get("after")
            return 200, {"frames": self.frames(after=after)}
        if method == "POST" and path == "/wake":
            reason = body.get("reason", "external")
            self.wake(reason)
            return 200, {"status": "accepted"}
        if method == "POST" and path == "/stop":
            self.stop()
            return 200, {"status": "stopping"}
        if method == "GET" and path == "/state/compactions":
            fs = self._cell.get("_frame_stream")
            return 200, ({} if fs is None else fs.project_compactions())
        if method == "POST" and path == "/reload/soul":
            self.reload_soul()
            return 200, {"status": "soul_reloaded"}
        if method == "POST" and path == "/reload/skill":
            name = (body or {}).get("name")
            if not isinstance(name, str) or not name:
                return 400, {"error": "missing 'name' in body"}
            ok = self.reload_skill(name)
            return (200 if ok else 404), {"status": "skill_reloaded" if ok else "not_loaded", "name": name}

        if method == "GET" and path == "/skills/list":
            entries = []
            for name in self._skill_manager.loaded_names:
                skill_dir = self._skill_manager.skill_dir(name)
                has_ui = bool(skill_dir and (Path(skill_dir) / "ui" / "index.html").exists())
                summary = getattr(self._skill_manager, "skill_summary", lambda _n: "")(name)
                entries.append({"name": name, "summary": summary or "", "has_ui": has_ui})
            return 200, {"skills": entries}

        if method == "GET" and path == "/skills/ui":
            entries = []
            for name in self._skill_manager.loaded_names:
                skill_dir = self._skill_manager.skill_dir(name)
                if skill_dir and (Path(skill_dir) / "ui" / "index.html").exists():
                    entries.append({"name": name, "url": f"/skills/{name}/ui/index.html"})
            return 200, {"skills": entries}

        return 404, {"error": f"not found: {method} {path}"}

    @property
    def event_queue(self):
        """The queue Shell uses to push events; thread-safe (stdlib queue.Queue).

        Returns:
            The queue.Queue instance inside EventLoop.
        """
        return self._event_loop.event_queue

    def _rewrite_runtime_owned(self) -> None:
        """Re-fill runtime-owned variables each frame: _frame_type, _render_config, _system_prompt, _soul.

        Hull is the source of truth for these variables; the model may read but should not modify them.
        """
        self._cell.set("_frame_type", "work")
        self._cell.set("_render_config", self._work_render_config)
        self._cell.set("_system_prompt", self._prompt_builder.build(self._cell.ns))
        # SOUL hot-reload: detect SOUL.md changes each frame (mtime check ~1μs).
        # Re-read on change; otherwise use cached value.
        if self._soul_path.exists():
            current_mtime = self._soul_path.stat().st_mtime
            if current_mtime != self._soul_mtime:
                self._soul_text = self._soul_path.read_text(encoding="utf-8")
                self._soul_mtime = current_mtime
        self._cell.set("_soul", self._soul_text)

        # Drain compaction result queue and apply to FrameStream
        fs = self._cell.get("_frame_stream")
        if fs is None:
            return
        results_to_apply: list[tuple[dict, int]] = []
        aborted = False
        while True:
            try:
                item = self._result_queue.get_nowait()
            except queue.Empty:
                break
            record, layer = item
            if record in ("skip", "error"):
                aborted = True
                continue
            results_to_apply.append((record, layer))
        if aborted and not results_to_apply:
            fs.abort_compaction()
        if results_to_apply:
            fs.apply_results(results_to_apply)
            s = fs.stats()
            frame_number = self._cell.get("_frame", 0)
            self._tracer.log(frame_number, "compaction.layer_stats", "gauge", -1,
                             f"hot={s['hot_counts']},cold={s['cold_counts']}")
            self.snapshot()
            self._compaction_frames_since_snapshot = 0

    def _after_frame(self) -> None:
        """Called after each successful frame. Evaluates try_shift and submits compaction task if due."""
        fs = self._cell.get("_frame_stream")
        if fs is None:
            return
        frame_number = self._cell.get("_frame", 0)
        task = fs.try_shift()
        if task is None:
            if len(fs._hot[0]) >= fs.k and fs.in_flight:
                self._tracer.log(frame_number, "compaction.shift_blocked", "gauge", -1, "value=1")
        else:
            self._tracer.log(frame_number, "compaction.in_flight", "gauge", -1, "value=1")
            raw = task.get("raw_bytes", 0)
            stripped = task.get("stripped_bytes", 0)
            if raw > 0:
                self._tracer.log(frame_number, "compaction.stripping_ratio", "gauge", -1,
                                 f"raw={raw},stripped={stripped}")
            self._thread_pool.submit(self._run_compaction_task, task, frame_number)
        self._compaction_frames_since_snapshot += 1
        if self._compaction_frames_since_snapshot >= self._compaction_snapshot_every_n:
            self.snapshot()
            self._compaction_frames_since_snapshot = 0
