"""skill_loader.py — Skill lifecycle management: discovery, loading, and unloading of Skill packages."""
from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _install_packages(packages: list[str]) -> None:
    """Install packages via pip and refresh the import cache."""
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", *packages])
    importlib.invalidate_caches()


def _parse_skill_md(path: Path) -> tuple[dict, str]:
    """Parse frontmatter and body from SKILL.md.

    Supports v0 (flat key: value) and v1 (with nested requires block).
    Nested blocks are detected by indentation (2+ spaces).
    """
    if not path.exists():
        return {}, ""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text.strip()

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text.strip()

    meta: dict = {}
    current_block: str | None = None
    block_dict: dict = {}

    for line in parts[1].strip().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Indented line → belongs to current_block
        if line.startswith("  ") and current_block is not None:
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                val = val.strip()
                # Parse inline list: [a, b, c]
                if val.startswith("[") and val.endswith("]"):
                    items = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
                    block_dict[key.strip()] = items
                else:
                    block_dict[key.strip()] = val.strip('"').strip("'")
            continue

        # Flush previous block
        if current_block is not None:
            meta[current_block] = block_dict
            current_block = None
            block_dict = {}

        # Top-level line
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            val = val.strip()
            if val:
                meta[key.strip()] = val.strip('"').strip("'")
            else:
                # Start of a nested block
                current_block = key.strip()
                block_dict = {}

    # Flush final block
    if current_block is not None:
        meta[current_block] = block_dict

    body = parts[2].strip()
    return meta, body


class SkillLoader:
    """Skill lifecycle manager: discovers, loads, and unloads Skill packages.

    Attributes:
        _skill_paths: List of directory paths to search for Skill packages.
        _loaded: Metadata dict of loaded Skills (name → {path, parent_added, parent_path}).
    """

    def __init__(self, skill_paths: list[str] | None = None):
        self._skill_paths = list(skill_paths or [])
        self._loaded: dict[str, dict] = {}  # name -> {path, parent_added, parent_path}
        # Pre-add all skill parent directories to sys.path so cloudpickle can find
        # bare module names (e.g. "chat", "memory") when restoring a snapshot.
        for sp in self._skill_paths:
            sp_str = str(sp)
            if sp_str not in sys.path:
                sys.path.insert(0, sp_str)

    @property
    def skill_paths(self) -> list[str]:
        """Skill search path list."""
        return self._skill_paths

    @skill_paths.setter
    def skill_paths(self, value: list[str]) -> None:
        """Set the Skill search path list.

        Args:
            value: New path list.
        """
        self._skill_paths = list(value)

    def list(self) -> list[dict]:
        """List all available Skills (reads SKILL.md only; does not trigger import).

        Returns:
            List of dicts for each Skill, format: [{"name": str, "description": str}, ...].
        """
        results = []
        seen: set[str] = set()

        for sp in self._skill_paths:
            sp_path = Path(sp).expanduser()
            if not sp_path.exists():
                continue
            for child in sorted(sp_path.iterdir()):
                if not child.is_dir() or child.name.startswith("_"):
                    continue
                resolved = str(child.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)

                skill_md = child / "SKILL.md"
                if not skill_md.exists():
                    continue

                meta, _ = _parse_skill_md(skill_md)
                results.append({
                    "name": meta.get("name", child.name),
                    "description": meta.get("description", ""),
                })

        return results

    def load(self, name: str) -> type:
        """Load a Skill package and return the SkillBase subclass (without instantiating).

        Process: first searches skill_paths (user skills); if not found, falls back to
        vessal.skills.<name> package (built-in skills). Built-in skills are imported using
        their full package path so cloudpickle records a stable module name, without relying on sys.path tricks.

        Args:
            name: Skill package name — corresponds to a subdirectory under skill_paths or a vessal.skills subpackage.

        Returns:
            SkillBase subclass.

        Raises:
            RuntimeError: Skill not found or import failed.
        """
        import importlib.util as _ilu

        # Search: check skill_paths first (user skills)
        skill_dir = None
        parent_path = None
        is_package_skill = False
        for sp in self._skill_paths:
            candidate = Path(sp).expanduser() / name
            if candidate.is_dir() and (candidate / "__init__.py").exists():
                skill_dir = candidate
                parent_path = Path(sp).expanduser()
                break

        # Fallback: load from the vessal.skills package (built-in skills)
        if skill_dir is None:
            pkg_name = f"vessal.skills.{name}"
            spec = _ilu.find_spec(pkg_name)
            if spec is None or spec.origin is None:
                raise RuntimeError(
                    f"Skill {name!r} not found in search paths: {self._skill_paths}, "
                    f"and not in vessal.skills package"
                )
            skill_dir = Path(spec.origin).parent  # .../vessal/skills/chat/
            is_package_skill = True

        # Check requires.skills dependencies before loading
        skill_md_path = skill_dir / "SKILL.md"
        meta, body = _parse_skill_md(skill_md_path)
        requires = meta.get("requires", {})
        if isinstance(requires, dict):
            required_skills = requires.get("skills", [])
            if isinstance(required_skills, list):
                for dep in required_skills:
                    if dep not in self._loaded:
                        raise RuntimeError(
                            f"Skill '{name}' requires skill '{dep}', but '{dep}' is not loaded. "
                            f"Load '{dep}' first."
                        )

        # Unload old version
        if name in self._loaded:
            self.unload(name)

        # Install dependencies (supported from both sources)
        req_file = skill_dir / "requirements.txt"
        if req_file.exists():
            lines = [
                line.strip()
                for line in req_file.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            if lines:
                _install_packages(lines)

        if is_package_skill:
            # Package skill: import directly using full package path; cloudpickle records a stable fully-qualified name
            import_name = f"vessal.skills.{name}"
            parent_added = False
            parent_str = None
        else:
            # User skill: sys.path manipulation + bare name import
            import_name = name
            parent_str = str(parent_path)
            parent_added = parent_str not in sys.path
            if parent_added:
                sys.path.insert(0, parent_str)

            # Clear sys.modules cache (ensure fresh reload)
            stale = [k for k in sys.modules if k == name or k.startswith(name + ".")]
            for k in stale:
                del sys.modules[k]

        importlib.invalidate_caches()

        # Import
        try:
            module = importlib.import_module(import_name)
        except Exception as e:
            if not is_package_skill and parent_added and parent_str in sys.path:
                sys.path.remove(parent_str)
            raise RuntimeError(f"load({name!r}) failed: {e}") from e

        # Get the Skill class
        skill_cls = getattr(module, "Skill", None)
        if skill_cls is None:
            raise RuntimeError(
                f"Skill {name!r} __init__.py does not export 'Skill' (from .skill import XxxClass as Skill)"
            )

        # Set guide from SKILL.md body (Agent queries via print(name.guide))
        if body:
            skill_cls.guide = body

        # Record
        self._loaded[name] = {
            "path": str(skill_dir),
            "parent_added": parent_added,
            "parent_path": parent_str,
            "is_package_skill": is_package_skill,
        }

        return skill_cls

    def unload(self, name: str) -> None:
        """Unload a Skill: clean up sys.modules cache and sys.path entries.

        Args:
            name: Name of the loaded Skill.
        """
        info = self._loaded.get(name, {})

        # Clean sys.modules (user skills use bare name import; package skills use fully-qualified name)
        if info.get("is_package_skill"):
            pkg_prefix = f"vessal.skills.{name}"
            to_remove = [k for k in sys.modules if k == pkg_prefix or k.startswith(pkg_prefix + ".")]
        else:
            to_remove = [k for k in sys.modules if k == name or k.startswith(name + ".")]
        for k in to_remove:
            del sys.modules[k]

        # Clean sys.path (only user skills modify sys.path)
        if info.get("parent_added") and info.get("parent_path"):
            parent_str = info["parent_path"]
            other_uses = any(
                v.get("parent_path") == parent_str
                for k, v in self._loaded.items()
                if k != name
            )
            if not other_uses and parent_str in sys.path:
                sys.path.remove(parent_str)

        self._loaded.pop(name, None)

    def reload(self, name: str) -> None:
        """Reload a skill's module by unloading it; caller re-instantiates via load().

        Module name is not explicitly tracked, so unload() clears sys.modules
        entries, then the next load() call imports fresh.
        """
        self.unload(name)

    @property
    def loaded_names(self) -> list[str]:
        """List of currently loaded skill names."""
        return list(self._loaded.keys())

    def skill_dir(self, name: str) -> str | None:
        """Return the directory path for a loaded skill, or None if not loaded."""
        entry = self._loaded.get(name)
        return entry["path"] if entry else None

    def has_server(self, name: str) -> bool:
        """Check whether a Skill has a server.py module.

        For loaded skills, checks the path recorded in _loaded; otherwise searches skill_paths.

        Args:
            name: Skill name.

        Returns:
            True if server.py exists in the Skill's directory.
        """
        if name in self._loaded:
            return (Path(self._loaded[name]["path"]) / "server.py").exists()
        for base in self._skill_paths:
            if (Path(base) / name / "server.py").exists():
                return True
        return False

    def load_server_module(self, name: str) -> Any:
        """Dynamically import a Skill's server.py module.

        For loaded skills, checks the path recorded in _loaded; otherwise searches skill_paths.

        Args:
            name: Skill name.

        Returns:
            The loaded server module, or None if not found.
        """
        import importlib.util
        server_path = None
        if name in self._loaded:
            candidate = Path(self._loaded[name]["path"]) / "server.py"
            if candidate.exists():
                server_path = candidate
        else:
            for base in self._skill_paths:
                candidate = Path(base) / name / "server.py"
                if candidate.exists():
                    server_path = candidate
                    break

        if server_path is None:
            return None

        module_name = f"_vessal_skill_{name}_server"
        spec = importlib.util.spec_from_file_location(module_name, server_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        return None
