"""hull.py — Hull configuration layer and lifecycle management: reads hull.toml, initializes Cell, drives the event loop."""
from __future__ import annotations

import logging
import queue
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

from vessal.ark.shell.hull.cell import Cell
from vessal.ark.shell.hull.cell.kernel.compression_parser import CompactionParseError, parse_compaction_json
from vessal.ark.shell.hull.event_loop import EventLoop, FrameHooks
from vessal.ark.shell.hull.skills_manager import SkillsManager
from vessal.ark.shell.hull.skill_manager import SkillManager
from vessal.ark.shell.hull.cell.kernel import RenderConfig
from vessal.ark.shell.hull.cell.kernel.render.prompt import Section, SystemPromptBuilder, render_capabilities
from vessal.ark.util.logging import Tracer


# Hull-level system prompt loaded from file (prompts/system.md)
_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    """Load a prompt file from the prompts/ directory. Returns an empty string if the file does not exist."""
    path = _PROMPTS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


class Hull:
    """Agent runtime orchestrator: reads hull.toml, configures Cell, drives the event loop.

    Attributes:
        _cell: Cell instance — the Agent's frame execution engine.
        _event_loop: EventLoop instance — drives the sleep/wake lifecycle.
        _skill_manager: SkillManager instance — manages Skill discovery and loading.
        _tracer: Tracer instance — records frame execution trace logs.
        _routes: Dynamic route table registered by Skill servers via HullApi.
    """

    def __init__(self, project_dir: str = ".") -> None:
        self._project_dir = Path(project_dir).resolve()

        config = self._init_config()

        core_cfg = config.get("core", {})
        cell_cfg = config.get("cell", {})
        hull_cfg = config.get("hull", {})
        renderer_cfg = config.get("renderer", {})
        agent_cfg = config.get("agent", {})
        gates_cfg = config.get("gates", {})

        self._init_cell(core_cfg, cell_cfg, agent_cfg)
        self._init_compression(hull_cfg)
        self._init_skills(hull_cfg)
        self._init_prompts(renderer_cfg)
        self._init_loop(gates_cfg)
        self._resume_pending_compaction()

    # ------------------------------------------------------------------ Initialization phases

    def _init_config(self) -> dict:
        """Phase 1: Load config, .env, activate venv. Pure config reads, no side effects on Cell."""
        config = self._load_config()

        env_path = self._project_dir / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        self._activate_venv()
        return config

    def _init_cell(self, core_cfg: dict, cell_cfg: dict, agent_cfg: dict) -> None:
        """Phase 2: Create Cell, setup logging/tracer, restore snapshot, inject agent vars."""
        api_params = core_cfg.get("api_params", {
            "temperature": cell_cfg.get("temperature", 0.7),
            "max_tokens": cell_cfg.get("max_tokens", 4096),
        })
        self._cell = Cell(
            timeout=core_cfg.get("timeout", 60.0),
            core_max_retries=core_cfg.get("max_retries", 3),
            api_params=api_params,
        )

        self._log_dir = str(self._project_dir / "logs")
        self._max_frames = cell_cfg.get("max_frames", 100)
        trace_enabled = cell_cfg.get("trace", True)
        self._tracer = Tracer(self._log_dir, enabled=trace_enabled)
        self._ensure_log_readme()

        if "context_budget" in cell_cfg:
            self._cell.set("_context_budget", cell_cfg["context_budget"])
        else:
            logger.warning(
                "hull.toml missing [cell].context_budget; using default 128000. "
                "Recommend setting a value matching the actual context window of OPENAI_MODEL."
            )

        self._snapshots_dir = self._project_dir / "snapshots"
        self._restore_latest_snapshot()

        if "language" in agent_cfg:
            self._cell.set("language", agent_cfg["language"])

    def _init_compression(self, hull_cfg: dict) -> None:
        """Phase 2b: Create compression Core, result queue, and single-worker ThreadPoolExecutor."""
        from vessal.ark.shell.hull.cell.core import Core
        self._compression_core = Core(
            timeout=float(hull_cfg.get("compression_timeout", 120.0)),
            max_retries=int(hull_cfg.get("compression_max_retries", 2)),
            api_params={
                "temperature": float(hull_cfg.get("compression_temperature", 0.3)),
                "max_tokens": int(hull_cfg.get("compression_max_tokens", 2048)),
            },
        )
        self._result_queue: queue.Queue = queue.Queue()
        self._thread_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="compaction")
        self._compaction_frames_since_snapshot = 0
        self._compaction_snapshot_every_n = int(hull_cfg.get("snapshot_every_n_frames", 20))
        prompt_path = Path(__file__).parent / "prompts" / "compression.md"
        self._compression_prompt = prompt_path.read_text(encoding="utf-8")
        self._cell.set("_compression_prompt", self._compression_prompt)

    def _init_skills(self, hull_cfg: dict) -> None:
        """Phase 3: SkillManager, SkillsManager, route table, pre-load Skills, start servers."""
        skill_paths = hull_cfg.get("skill_paths", [])
        resolved_paths = [str(self._project_dir / p) for p in skill_paths] if skill_paths else []

        self._skill_manager = SkillManager(skill_paths=resolved_paths)
        self._cell.set("_builtin_names", ["skills"])

        _skills = SkillsManager(self)
        self._cell.set("skills", _skills)
        self._cell.set("skill_paths", resolved_paths)
        self._cell.set("_data_dir", str(self._project_dir / "data"))
        compress_threshold = hull_cfg.get("compress_threshold", 50)
        self._cell.set("_compress_threshold", compress_threshold)
        self._cell.set("_compaction_k", hull_cfg.get("compaction_k", 16))
        self._cell.set("_compaction_n", hull_cfg.get("compaction_n", 8))

        self._routes: dict[tuple[str, str], Any] = {}
        self._running_servers: dict[str, Any] = {}
        self._server_kwargs: dict[str, dict] = {
            "heartbeat": {"heartbeat": hull_cfg.get("heartbeat", 1800.0)},
        }
        from vessal.ark.shell.hull.hull_api import HullApi
        self._hull_api = HullApi(routes=self._routes, wake_fn=self.wake)

        for skill_name in hull_cfg.get("skills", []):
            restored = skill_name in self._cell.ns
            try:
                if restored:
                    self._skill_manager.load(skill_name)
                    description = getattr(type(self._cell.ns[skill_name]), "description", "")
                    print(f"{skill_name} loaded — {description}")
                else:
                    self._load_and_instantiate_skill(skill_name)
            except Exception as e:
                print(f"[error] skill '{skill_name}' failed to load, skipping: {e}", flush=True)
                continue
            if self._skill_manager.has_server(skill_name):
                try:
                    self._start_skill_server(skill_name)
                    print(f"  └─ routes: /skills/{skill_name}/", flush=True)
                except Exception as e:
                    print(f"[error] skill server '{skill_name}' failed to start: {e}", flush=True)

    def _init_prompts(self, renderer_cfg: dict) -> None:
        """Phase 4: Load system prompts, SOUL, build RenderConfig."""
        protocol_text = _load_prompt("system.md")
        # SOUL hot-reload: record path and mtime so _rewrite_runtime_owned
        # can detect file changes each frame and re-read, rather than always using the cached value from init.
        self._soul_path = self._project_dir / "SOUL.md"
        if self._soul_path.exists():
            self._soul_text = self._soul_path.read_text(encoding="utf-8")
            self._soul_mtime = self._soul_path.stat().st_mtime
        else:
            self._soul_text = ""
            self._soul_mtime = 0.0

        self._prompt_builder = SystemPromptBuilder()
        self._prompt_builder.register(Section("protocol", 0, True, lambda ns: protocol_text))
        self._prompt_builder.register(Section("capabilities", 20, False, render_capabilities))

        self._work_render_config = RenderConfig(
            system_prompt_key=renderer_cfg.get("system_prompt_key", "_system_prompt"),
            frame_budget_ratio=renderer_cfg.get("frame_budget_ratio", 0.7),
        )

    def _init_loop(self, gates_cfg: dict) -> None:
        """Phase 5: Gates, FrameHooks, EventLoop, wake injection."""
        if "state_gate" in gates_cfg:
            self._cell.state_gate = gates_cfg["state_gate"]
        if "action_gate" in gates_cfg:
            self._cell.action_gate = gates_cfg["action_gate"]
        self._load_gate_files()

        self._rewrite_runtime_owned()

        hooks = FrameHooks(
            before_frame=self._rewrite_runtime_owned,
            after_frame=self._after_frame,
            snapshot=self.snapshot,
        )

        self._event_loop = EventLoop(
            cell=self._cell,
            max_frames_per_wake=self._max_frames,
            tracer=self._tracer,
            hooks=hooks,
        )

        self._cell.set("_inject_wake", lambda reason="user_message": self.wake(reason))

    # ------------------------------------------------------------------ Public interface

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

    # ── Skill management public API (used by SkillsManager) ──

    def loaded_skill_names(self) -> list[str]:
        """Return names of currently loaded Skills."""
        return self._skill_manager.loaded_names()

    def available_skills(self) -> list[dict]:
        """Return list of available Skills (name + description)."""
        return self._skill_manager.list()

    def load_skill(self, name: str) -> None:
        """Load a Skill: instantiate into namespace + start server."""
        self._load_and_instantiate_skill(name)

    def has_skill_server(self, name: str) -> bool:
        """Check if a Skill has a server component."""
        return self._skill_manager.has_server(name)

    def start_skill_server(self, name: str) -> None:
        """Start a Skill's HTTP server."""
        self._start_skill_server(name)

    def stop_skill_server(self, name: str) -> None:
        """Stop a Skill's HTTP server."""
        self._stop_skill_server(name)

    def unload_skill_from_manager(self, name: str) -> None:
        """Unload a Skill from the SkillManager registry."""
        self._skill_manager.unload(name)

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
        if method == "GET" and path == "/frames":
            after = body.get("after")
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
        if method == "GET" and path == "/logs":
            return self._handle_logs_viewer()
        if method == "GET" and path == "/logs/raw":
            after = body.get("after") if body else None
            return self._handle_logs_raw(after=after)

        return 404, {"error": f"not found: {method} {path}"}

    def _handle_logs_viewer(self) -> tuple[int, "StaticResponse"]:
        """GET /logs — Return the HTML viewer content.

        Returns:
            (200, StaticResponse) containing viewer.html content.
        """
        from vessal.ark.shell.hull.hull_api import StaticResponse
        viewer_path = Path(__file__).parent.parent.parent / "util" / "logging" / "viewer.html"
        if not viewer_path.exists():
            return 404, StaticResponse(b"viewer.html not found", "text/plain")
        content = viewer_path.read_bytes()
        return 200, StaticResponse(content, "text/html; charset=utf-8")

    def _handle_logs_raw(self, after: int | None = None) -> tuple[int, "StaticResponse"]:
        """GET /logs/raw[?after=N] — Return frames.jsonl content (supports incremental reads).

        Args:
            after: Line offset; return content starting from line `after` (0-indexed). Returns all if None.

        Returns:
            (200, StaticResponse) containing JSONL text.
        """
        from vessal.ark.shell.hull.hull_api import StaticResponse
        path = Path(self._log_dir) / "frames.jsonl"
        if not path.exists():
            return 200, StaticResponse(b"", "text/plain; charset=utf-8")
        lines = path.read_text(encoding="utf-8").splitlines()
        if after is not None and isinstance(after, int) and after > 0:
            lines = lines[after:]
        content = "\n".join(lines)
        if content:
            content += "\n"
        return 200, StaticResponse(content.encode("utf-8"), "text/plain; charset=utf-8")

    def snapshot(self, path: str | None = None) -> str:
        """Save a snapshot to disk.

        Args:
            path: Snapshot file path. If None, auto-generates a timestamped filename under snapshots/.

        Returns:
            The actual file path written as a string.
        """
        if path is None:
            self._snapshots_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = str(self._snapshots_dir / f"{timestamp}.pkl")
        self._cell.snapshot(path)
        return path

    @property
    def event_queue(self):
        """The queue Shell uses to push events; thread-safe (stdlib queue.Queue).

        Returns:
            The queue.Queue instance inside EventLoop.
        """
        return self._event_loop.event_queue

    def _start_skill_server(self, name: str) -> bool:
        """Start a skill's server. Returns True if started. Raises on failure."""
        if name in self._running_servers:
            return True  # already running, skip
        if not self._skill_manager.has_server(name):
            return False
        mod = self._skill_manager.load_server_module(name)
        if mod is None or not hasattr(mod, "start"):
            raise RuntimeError(f"skill '{name}' has server.py but no start() function")
        kwargs = dict(self._server_kwargs.get(name, {}))
        # Create a dedicated ScopedHullApi for each skill, auto-prefixing /skills/{name}/
        from vessal.ark.shell.hull.hull_api import ScopedHullApi
        scoped_api = ScopedHullApi(self._hull_api, name)
        # Only pass the skill instance if server.start() declares a skill parameter
        import inspect
        start_params = inspect.signature(mod.start).parameters
        if "skill" in start_params:
            skill_instance = self._cell.ns.get(name)
            if skill_instance is not None:
                kwargs["skill"] = skill_instance
        mod.start(scoped_api, **kwargs)
        self._running_servers[name] = mod
        logger.info("skill server '%s' started", name)
        return True

    def _stop_skill_server(self, name: str) -> None:
        """Stop a skill's server."""
        mod = self._running_servers.pop(name, None)
        if mod is not None and hasattr(mod, "stop"):
            try:
                mod.stop()
                logger.info("skill server '%s' stopped", name)
            except Exception as e:
                logger.warning("skill server '%s' failed to stop: %s", name, e)

    # ------------------------------------------------------------------ Runtime-owned variables

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

    # ------------------------------------------------------------------ Internal helpers

    def _ensure_log_readme(self) -> None:
        """Ensure the logs directory has a README.md file."""
        log_dir = Path(self._log_dir)
        readme_path = log_dir / "README.md"
        if readme_path.exists():
            return
        log_dir.mkdir(parents=True, exist_ok=True)
        readme_path.write_text(
            """# Vessal Log Directory

This directory contains various log files from Agent execution.

## File types

| Suffix | Purpose | Format |
|--------|---------|--------|
| `.jsonl` | Structured frame logs for programmatic analysis | JSON Lines (canonical FrameRecord format) |
| `.trace.log` | Execution traces for debugging performance | timestamp|frame|phase|event|ms|details |

## Configuration

Adjust in hull.toml [cell]:

```toml
[cell]
trace = true   # enable trace logs (default)
trace = false  # disable to reduce IO
```
""",
            encoding="utf-8",
        )

    def _load_config(self) -> dict:
        """Read hull.toml; return an empty dict if it does not exist."""
        toml_path = self._project_dir / "hull.toml"
        if not toml_path.exists():
            return {}
        with open(toml_path, "rb") as f:
            return tomllib.load(f)

    def _restore_latest_snapshot(self) -> None:
        """Detect and restore the latest .pkl file under snapshots/. Silently skips if none exist."""
        if not self._snapshots_dir.exists():
            return
        snapshots = sorted(self._snapshots_dir.glob("*.pkl"))
        if snapshots:
            self._cell.restore(str(snapshots[-1]))

    def _load_and_instantiate_skill(self, name: str) -> None:
        """Load and instantiate a Skill. Pre-loaded skills are automatically placed into namespace."""
        import inspect
        try:
            skill_cls = self._skill_manager.load(name)
            sig = inspect.signature(skill_cls.__init__)
            params = [p for p in sig.parameters if p != "self"]
            if params and "ns" in sig.parameters:
                instance = skill_cls(ns=self._cell.ns)
            else:
                instance = skill_cls()
            self._cell.set(name, instance)
            description = getattr(skill_cls, "description", "")
            print(f"{name} loaded — {description}")
        except Exception as e:
            raise RuntimeError(f"skill '{name}' failed to load: {e}") from e

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

    def _resume_pending_compaction(self) -> None:
        """Re-submit any in-flight compaction that survived in the snapshot after a crash-restart."""
        fs = self._cell.get("_frame_stream")
        if fs is None:
            return
        if fs.compression_zone is None:
            return
        frame_number = self._cell.get("_frame", 0)
        payload = list(fs.compression_zone)
        task = {"layer": 0, "payload": payload}
        self._thread_pool.submit(self._run_compaction_task, task, frame_number)
        self._tracer.log(frame_number, "compaction.resumed", "event", 0, f"payload_n={len(payload)}")

    def _run_compaction_task(self, task: dict, frame_number: int) -> None:
        """Compaction worker body. Runs on the compaction thread. Must not touch ns."""
        import time
        layer = task["layer"]
        payload = task["payload"]
        if not payload:
            self._result_queue.put(("skip", layer))
            return
        ping = self._build_compression_ping(payload, layer)
        t0 = time.monotonic()
        try:
            pong, _p, _c = self._compression_core.run(ping, tracer=self._tracer, frame=frame_number)
            raw_json = pong.action.operation
            record = parse_compaction_json(raw_json, layer=layer, compacted_at=frame_number)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            self._tracer.log(frame_number, "compaction.latency_ms", "span", elapsed_ms,
                             f"layer={layer}")
            self._result_queue.put((record.to_dict(), layer))
        except (CompactionParseError, Exception) as e:
            self._tracer.log(frame_number, "compaction.error", "worker", -1, f"layer={layer} err={e!r}")
            self._result_queue.put(("error", layer))

    def _build_compression_ping(self, payload: list[dict], layer: int) -> "Ping":
        """Assemble a compression Ping from a stripped frame or cold record payload."""
        from vessal.ark.shell.hull.cell.protocol import Ping, State
        from vessal.ark.shell.hull.cell.kernel.render._frame_render import project_frame_dict
        from vessal.ark.shell.hull.cell.kernel.render._cold_render import project_compaction_record

        if layer == 0:
            body = "\n\n".join(project_frame_dict(f) for f in payload)
        else:
            body = "\n\n".join(project_compaction_record(r) for r in payload)
        return Ping(
            system_prompt=self._compression_prompt,
            state=State(
                frame_stream="══════ frame stream ══════\n" + body,
                signals="",
            ),
        )

    def _activate_venv(self) -> None:
        """Add the project .venv's site-packages to sys.path.

        Makes packages installed into .venv importable (e.g., by the pip Skill).
        Silently skips if .venv does not exist.
        """
        venv_path = self._project_dir / ".venv"
        if not venv_path.exists():
            return

        if sys.platform == "win32":
            site_packages = venv_path / "Lib" / "site-packages"
        else:
            py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
            site_packages = venv_path / "lib" / py_ver / "site-packages"

        if site_packages.exists() and str(site_packages) not in sys.path:
            import site as site_mod
            site_mod.addsitedir(str(site_packages))

    def _load_gate_files(self) -> None:
        """Read Python gate files from the gates/ directory and register them via cell.set_gate().

        Scans gates/action_gate.py and gates/state_gate.py,
        extracts the check() function and registers it as a custom gate rule.
        Silently returns if the gates/ directory does not exist;
        logs a warning if a file is missing check() or fails to execute.
        """
        gates_dir = Path(self._project_dir) / "gates"
        if not gates_dir.is_dir():
            return

        for gate_type in ("action_gate", "state_gate"):
            gate_file = gates_dir / f"{gate_type}.py"
            if not gate_file.exists():
                continue

            try:
                code = gate_file.read_text(encoding="utf-8")
                ns: dict = {}
                exec(compile(code, str(gate_file), "exec"), ns)

                check_fn = ns.get("check")
                if check_fn is None or not callable(check_fn):
                    logger.warning("gates/%s.py missing check() function, skipping", gate_type)
                    continue

                self._cell.set_gate(gate_type.replace("_gate", ""), check_fn)
                logger.info("Loaded custom gate: %s", gate_type)
            except Exception as e:
                logger.warning("Failed to load gates/%s.py: %s", gate_type, e)

