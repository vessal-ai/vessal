"""hull_skills_mixin.py — Skill load/unload/reload + server lifecycle for Hull.

Part of the Hull class via multiple-inheritance composition (see hull.py).
Methods here may assume the attributes set by Hull.__init__ are available via self.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:

    pass

logger = logging.getLogger(__name__)


class HullSkillsMixin:
    """Skill management for Hull: load/unload/reload + HTTP server lifecycle."""

    def loaded_skill_names(self) -> list[str]:
        """Return names of currently loaded Skills."""
        return self._skill_manager.loaded_names

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
        """Unload a Skill from the SkillLoader registry."""
        self._skill_manager.unload(name)

    def reload_skill(self, name: str) -> bool:
        """Reload a skill by name. Returns True if the skill was reloaded."""
        # NOTE: loaded_names is a @property on SkillLoader (no parens).
        if name not in self._skill_manager.loaded_names:
            return False
        try:
            self._stop_skill_server(name)
        except Exception:
            pass
        self._skill_manager.reload(name)
        self._load_and_instantiate_skill(name)
        return True

    def _load_and_instantiate_skill(self, name: str) -> None:
        """Load and instantiate a Skill. Pre-loaded skills are automatically placed into namespace.

        After setting the instance into namespace, calls instance._bind_hull(self) if the method
        exists. This allows Skills that need a Hull handle (e.g. the merged Skills(SkillBase) class)
        to receive it without exposing Hull in the user-facing namespace.
        """
        import inspect
        try:
            skill_cls = self._skill_manager.load(name)
            sig = inspect.signature(skill_cls.__init__)
            params = [p for p in sig.parameters if p != "self"]
            if params and "ns" in sig.parameters:
                instance = skill_cls(ns=self._cell.L)
            else:
                instance = skill_cls()
            self._cell.L[name] = instance
            bind = getattr(instance, "_bind_hull", None)
            if callable(bind):
                bind(self)
            description = getattr(skill_cls, "description", "")
            print(f"{name} loaded — {description}")
        except Exception as e:
            raise RuntimeError(f"skill '{name}' failed to load: {e}") from e

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
            skill_instance = self._cell.L.get(name)
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
