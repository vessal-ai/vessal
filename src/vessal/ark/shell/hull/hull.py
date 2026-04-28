"""hull.py — Hull facade: constructs Cell, wires mixins, drives the event loop.

Hull is a single facade class (see tests/architecture/test_hull_facade.py).
Its ~40 methods are grouped into four mixins by theme:
  - HullInitMixin       — hull.toml + Cell + venv + gates wiring
  - HullSkillsMixin     — Skill load/unload/reload + server lifecycle
  - HullSnapshotMixin   — snapshot management
  - HullRuntimeMixin    — runtime-owned vars + event loop + HTTP.handle()

Callers only see Hull; the mixins are not re-exported.
"""
from __future__ import annotations

from pathlib import Path

from vessal.ark.shell.hull.hull_init_mixin import HullInitMixin
from vessal.ark.shell.hull.hull_skills_mixin import HullSkillsMixin
from vessal.ark.shell.hull.hull_snapshot_mixin import HullSnapshotMixin
from vessal.ark.shell.hull.hull_runtime_mixin import HullRuntimeMixin


class Hull(HullInitMixin, HullSkillsMixin, HullSnapshotMixin, HullRuntimeMixin):
    """Agent runtime orchestrator. See CONTEXT.md for the full responsibility statement."""

    def __init__(self, project_dir: str = ".") -> None:
        self._project_dir = Path(project_dir).resolve()

        config = self._init_config()

        core_cfg = config.get("core", {})
        cell_cfg = config.get("cell", {})
        hull_cfg = config.get("hull", {})
        agent_cfg = config.get("agent", {})
        gates_cfg = config.get("gates", {})

        cells_cfg = config.get("cells", {})

        boot_entries = self._init_skills_pre(hull_cfg)
        self._init_cell(core_cfg, cell_cfg, agent_cfg, cells_cfg, boot_entries)
        self._init_skills(hull_cfg)
        self._init_prompts()
        self._init_loop(gates_cfg)
