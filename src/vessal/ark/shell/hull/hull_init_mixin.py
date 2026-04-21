"""hull_init_mixin.py — Hull initialization phases: hull.toml, Cell, venv, gates wiring.

Part of the Hull class via multiple-inheritance composition (see hull.py).
Methods here may assume the attributes set by Hull.__init__ are available via self.
"""
from __future__ import annotations

import logging
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import queue


logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    """Load a prompt file from the prompts/ directory. Returns an empty string if the file does not exist."""
    path = _PROMPTS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


class HullInitMixin:
    """Initialization phases for Hull: config loading, Cell creation, venv, gates."""

    def _init_config(self) -> dict:
        """Phase 1: Load config, .env, activate venv. Pure config reads, no side effects on Cell."""
        from dotenv import load_dotenv
        config = self._load_config()

        env_path = self._project_dir / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        self._activate_venv()
        return config

    def _init_cell(self, core_cfg: dict, cell_cfg: dict, agent_cfg: dict) -> None:
        """Phase 2: Create Cell, setup logging/tracer, restore snapshot, inject agent vars."""
        from vessal.ark.shell.hull.cell import Cell
        from vessal.ark.util.logging import Tracer

        api_params = core_cfg.get("api_params", {
            "temperature": cell_cfg.get("temperature", 0.7),
            "max_tokens": cell_cfg.get("max_tokens", 4096),
        })
        self._cell = Cell(
            timeout=core_cfg.get("timeout", 60.0),
            core_max_retries=core_cfg.get("max_retries", 3),
            api_params=api_params,
        )
        self._cell.set("_error_buffer_cap", cell_cfg.get("error_buffer_cap", 200))

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
        self._cell.set("_token_budget", self._cell.max_tokens)

        if "language" in agent_cfg:
            self._cell.set("language", agent_cfg["language"])

    def _init_compression(self, hull_cfg: dict) -> None:
        """Phase 2b: Create compression Core, result queue, and single-worker ThreadPoolExecutor."""
        import queue
        from concurrent.futures import ThreadPoolExecutor
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
        """Phase 3: SkillLoader, route table, pre-load Skills, start servers."""
        from vessal.ark.shell.hull.skill_loader import SkillLoader
        from vessal.ark.shell.hull.hull_api import HullApi

        skill_paths = hull_cfg.get("skill_paths", [])
        resolved_paths = [str(self._project_dir / p) for p in skill_paths] if skill_paths else []

        self._skill_manager = SkillLoader(skill_paths=resolved_paths)
        self._cell.set("_builtin_names", [])

        self._cell.set("skill_paths", resolved_paths)
        self._cell.set("_data_dir", str(self._project_dir / "data"))
        compress_threshold = hull_cfg.get("compress_threshold", 50)
        self._cell.set("_compress_threshold", compress_threshold)
        if "compaction_k" in hull_cfg:
            self._cell.set("_compaction_k", hull_cfg["compaction_k"])
        if "compaction_n" in hull_cfg:
            self._cell.set("_compaction_n", hull_cfg["compaction_n"])

        self._routes: dict[tuple[str, str], object] = {}
        self._running_servers: dict[str, object] = {}
        self._server_kwargs: dict[str, dict] = {
            "heartbeat": {"heartbeat": hull_cfg.get("heartbeat", 1800.0)},
        }
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
        from vessal.ark.shell.hull.cell.kernel import RenderConfig
        from vessal.ark.shell.hull.cell.kernel.render.prompt import Section, SystemPromptBuilder, render_capabilities

        protocol_text = _load_prompt("system.md")
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
        from vessal.ark.shell.hull.event_loop import EventLoop, FrameHooks

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
