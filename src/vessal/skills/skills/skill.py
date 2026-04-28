"""skills Skill — inventory, hot-load/unload, and hub search."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from vessal.ark.shell.hull.hub.registry import Registry
from vessal.skills._base import BaseSkill

if TYPE_CHECKING:
    from vessal.ark.shell.hull.hull import Hull

logger = logging.getLogger(__name__)


class Skills(BaseSkill):
    """Agent-facing Skill management + Console-facing inventory UI."""

    name = "skills"
    description = "skill inventory"
    tools = ["load", "unload", "search_hub", "download_skill", "list_hub"]

    def __init__(self, ns: dict | None = None) -> None:
        super().__init__()
        self._ns = ns
        self._hull: "Hull | None" = None

    def _bind_hull(self, hull: "Hull") -> None:
        """Hull loader calls this exactly once after injection into ns."""
        self._hull = hull

    def _prompt(self) -> tuple[str, str] | None:
        return (
            "using a loaded skill",
            "Before using any skill for the first time, you must print(name.guide) to read the manual.\n"
            "Call methods with the exact names and parameters from the manual; do not guess the interface.",
        )

    def signal_update(self) -> None:
        if self._hull is None:
            self.signal = {}
            return
        available = self._hull.available_skills()
        loaded = self._hull.loaded_skill_names()
        lines = []
        for s in available:
            name = s.get("name", "?")
            desc = s.get("description", "")
            marker = "[loaded]" if name in loaded else "[available]"
            lines.append(f"  {marker} {name} — {desc}")
        lines.append("")
        lines.append("Before using a loaded skill for the first time, run print(name.guide) to view methods")
        text = "\n".join(lines)
        self.signal = {"available": text} if text else {}

    def list(self) -> list[dict]:
        """List all available Skills."""
        return self._hull.available_skills()

    def load(self, name: str) -> str:
        """Load a Skill into Cell namespace and start its server (if any)."""
        try:
            self._hull.load_skill(name)
        except Exception as e:
            return f"load failed: {e}"

        if self._hull.has_skill_server(name):
            try:
                self._hull.start_skill_server(name)
            except Exception as e:
                self._hull.set_ns(name, None)
                self._hull.unload_skill_from_manager(name)
                return f"skill server '{name}' failed to start, rolled back: {e}"

        return f"loaded {name}"

    def unload(self, name: str) -> str:
        """Unload a Skill: stop server, remove from namespace."""
        self._hull.stop_skill_server(name)

        instance = self._hull.get_ns(name)
        if instance is not None:
            declared_keys = getattr(instance, "ns_keys", [])
            for key in declared_keys:
                if key in self._hull.ns_keys():
                    self._hull.set_ns(key, None)
            self._hull.set_ns(name, None)

        self._hull.unload_skill_from_manager(name)
        return f"unloaded {name}"

    def search_hub(self, keyword: str) -> str:
        """Search the SkillHub registry for skills matching a keyword."""
        try:
            registry = Registry.fetch()
        except RuntimeError as e:
            return f"search failed: {e}"

        results = registry.search(keyword)
        if not results:
            return f"No skills found matching '{keyword}'"

        lines = [f"Found {len(results)} skill(s):"]
        for entry in results:
            tags = ", ".join(entry.get("tags", []))
            tag_str = f" [{tags}]" if tags else ""
            lines.append(f"  {entry['name']} — {entry.get('description', '')}{tag_str}")
        lines.append("")
        lines.append("To install: skills.download_skill('name')")
        return "\n".join(lines)

    def download_skill(self, name: str) -> str:
        """Download and install a skill from SkillHub."""
        from vessal.ark.shell.hull.hub.installer import install
        from vessal.ark.shell.hull.hub.resolver import resolve

        skill_paths = self._hull.get_ns("skill_paths")
        if not skill_paths:
            return "download failed: no skill_paths configured"

        hub_dir = None
        for sp in skill_paths:
            if sp.endswith("/hub") or sp.endswith("\\hub"):
                hub_dir = Path(sp)
                break
        if hub_dir is None:
            hub_dir = Path(skill_paths[0])

        try:
            resolved = resolve(name)
            return install(resolved, hub_dir)
        except RuntimeError as e:
            return f"download failed: {e}"

    def list_hub(self, page: int = 1) -> str:
        """List skills available on SkillHub with pagination."""
        try:
            registry = Registry.fetch()
        except RuntimeError as e:
            return f"list failed: {e}"

        entries = registry.list_paged(page=page, per_page=20)
        if not entries:
            return f"No more skills (page {page})"

        total = len(registry.list_all())
        lines = [f"SkillHub (page {page}, {total} total):"]
        for entry in entries:
            lines.append(f"  {entry['name']} — {entry.get('description', '')}")
        lines.append("")
        lines.append(f"Use skills.search_hub('keyword') to search, or skills.list_hub({page + 1}) for next page")
        return "\n".join(lines)
