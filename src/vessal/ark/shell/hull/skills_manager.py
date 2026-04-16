"""skills_manager.py — SkillsManager: Skill management interface callable by the Agent in the namespace."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vessal.ark.shell.hull.hull import Hull

logger = logging.getLogger(__name__)


class SkillsManager:
    """Agent's Skill manager: provides Skill management operations in the namespace.

    Attributes:
        name: Skill identifier ("skills").
        description: One-line description.
        tools: List of tool method names callable by the Agent.
        _hull: Hull instance reference; accessed via public interface only, not private attributes.
    """

    name = "skills"
    description = "skill lifecycle management"
    tools = ["load", "unload"]

    def __init__(self, hull: "Hull"):
        self._hull = hull

    def _prompt(self) -> tuple[str, str] | None:
        """Cognitive protocol: guides the Agent to use the Skill system correctly."""
        return (
            "using a loaded skill",
            "Before using any skill for the first time, you must print(name.guide) to read the manual.\n"
            "Call methods with the exact names and parameters from the manual; do not guess the interface."
        )

    def _signal(self) -> tuple[str, str] | None:
        """Output the available Skill list signal each frame. No method names; appends guide reminder."""
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
        return ("available skills", "\n".join(lines))

    def list(self) -> list[dict]:
        """List all available Skills (name + description); does not trigger import.

        Returns:
            List of dicts for each Skill, format: [{"name": str, "description": str}, ...].
        """
        return self._hull.available_skills()

    def load(self, name: str) -> str:
        """Load a Skill: inject into Cell namespace and start its server (if any).

        Two-phase load: phase 1 loads the class, instantiates and injects into namespace;
        phase 2 starts the server (if server.py exists).
        If phase 2 fails, phase 1 is rolled back to ensure no server-less instance remains in namespace.

        Args:
            name: Skill name — corresponds to a subdirectory under skill_paths.

        Returns:
            Result string (success contains "loaded"; failure contains "failed" and reason).
        """
        try:
            self._hull.load_skill(name)
        except Exception as e:
            return f"load failed: {e}"

        if self._hull.has_skill_server(name):
            try:
                self._hull.start_skill_server(name)
            except Exception as e:
                # Rollback phase 1
                self._hull.set_ns(name, None)
                self._hull.unload_skill_from_manager(name)
                return f"skill server '{name}' failed to start, rolled back: {e}"

        return f"loaded {name}"

    def unload(self, name: str) -> str:
        """Unload a Skill: stop its server and clean up the instance from namespace.

        Args:
            name: Name of the loaded Skill.

        Returns:
            Result string (contains "unloaded" and the Skill name).
        """
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
