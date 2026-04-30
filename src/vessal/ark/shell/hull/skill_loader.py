"""skill_loader.py — Skill lifecycle management: discovery, loading, and unloading of Skill packages."""
from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path

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
    """Skill lifecycle manager: load/unload Skill packages from <project>/skills/.

    Resolution model: every Skill lives at <project>/skills/<name>/__init__.py
    and exports `Skill`. Discovery is Python's native `importlib`; no skill_paths,
    no sys.path manipulation.
    """

    def __init__(self) -> None:
        self._loaded: dict[str, dict] = {}  # name -> {"path": str}

    def list(self) -> list[dict]:
        """List Skills present in <project>/skills/ by reading SKILL.md frontmatter."""
        import skills  # registered via .pth file
        skills_dir = Path(skills.__file__).parent
        results: list[dict] = []
        for child in sorted(skills_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("_"):
                continue
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
        """Import skills.<name> and return its `Skill` class.

        Reloads sys.modules entries first so a re-load picks up source edits.
        Installs requirements.txt if present.
        """
        if name in self._loaded:
            self.unload(name)

        module_name = f"skills.{name}"
        skill_dir = self._resolve_skill_dir(name)

        skill_md_path = skill_dir / "SKILL.md"
        meta, body = _parse_skill_md(skill_md_path)
        requires = meta.get("requires", {})
        if isinstance(requires, dict):
            for dep in requires.get("skills", []) or []:
                if dep not in self._loaded:
                    raise RuntimeError(
                        f"Skill '{name}' requires '{dep}', but '{dep}' is not loaded."
                    )

        req_file = skill_dir / "requirements.txt"
        if req_file.exists():
            lines = [
                ln.strip()
                for ln in req_file.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
            if lines:
                _install_packages(lines)

        # Force reload so source edits are picked up.
        stale = [k for k in sys.modules if k == module_name or k.startswith(module_name + ".")]
        for k in stale:
            del sys.modules[k]
        importlib.invalidate_caches()

        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            raise RuntimeError(f"load({name!r}) failed: {e}") from e

        skill_cls = getattr(module, "Skill", None)
        if skill_cls is None:
            raise RuntimeError(
                f"Skill {name!r} __init__.py does not export 'Skill' "
                f"(use `from .skill import XxxClass as Skill`)"
            )

        if body:
            skill_cls.guide = body

        self._loaded[name] = {"path": str(skill_dir)}
        return skill_cls

    def unload(self, name: str) -> None:
        """Drop the Skill from sys.modules so the next load() re-imports."""
        module_name = f"skills.{name}"
        stale = [k for k in sys.modules if k == module_name or k.startswith(module_name + ".")]
        for k in stale:
            del sys.modules[k]
        self._loaded.pop(name, None)

    def reload(self, name: str) -> None:
        self.unload(name)

    @property
    def loaded_names(self) -> list[str]:
        return list(self._loaded.keys())

    def skill_dir(self, name: str) -> str | None:
        entry = self._loaded.get(name)
        if entry:
            return entry["path"]
        try:
            return str(self._resolve_skill_dir(name))
        except RuntimeError:
            return None

    def has_server(self, name: str) -> bool:
        try:
            return (self._resolve_skill_dir(name) / "server.py").exists()
        except RuntimeError:
            return False

    def load_server_module(self, name: str):
        import importlib.util
        try:
            server_path = self._resolve_skill_dir(name) / "server.py"
        except RuntimeError:
            return None
        if not server_path.exists():
            return None
        module_name = f"_vessal_skill_{name}_server"
        spec = importlib.util.spec_from_file_location(module_name, server_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        return None

    def skill_summary(self, name: str) -> str:
        try:
            meta, _ = _parse_skill_md(self._resolve_skill_dir(name) / "SKILL.md")
            return meta.get("description", "")
        except RuntimeError:
            return ""

    def _resolve_skill_dir(self, name: str) -> Path:
        try:
            import skills  # registered via .pth file
        except ImportError as e:
            raise RuntimeError(
                "Cannot import 'skills' package — has the project venv been set up "
                "with `vessal create`? Expected vessal_user_skills.pth in site-packages."
            ) from e
        candidate = Path(skills.__file__).parent / name
        if not candidate.is_dir() or not (candidate / "__init__.py").exists():
            raise RuntimeError(f"Skill {name!r} not found at {candidate}")
        return candidate
