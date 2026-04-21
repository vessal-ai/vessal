"""test_no_ns_collision — every built-in Skill claims a unique `name`, disjoint from Hull-reserved keys."""
from __future__ import annotations

import importlib
from pathlib import Path


_SKILLS_DIR = Path(__file__).resolve().parents[2] / "src/vessal/skills"

_HULL_RESERVED = {
    "skill_paths",
    "_data_dir",
    "_compress_threshold",
    "_compaction_k",
    "_compaction_n",
    "_builtin_names",
    "_frame",
    "_wake",
    "_sleeping",
    "_frame_stream",
    "_system_prompt",
    "_render_config",
    "_frame_type",
    "_soul",
    "_context_budget",
    "_compression_prompt",
    "_next_wake",
    "_inject_wake",
    "language",
}


def _skill_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for pkg_dir in sorted(_SKILLS_DIR.iterdir()):
        if not pkg_dir.is_dir() or not (pkg_dir / "__init__.py").exists():
            continue
        mod = importlib.import_module(f"vessal.skills.{pkg_dir.name}")
        cls = getattr(mod, "Skill", None)
        if cls is None:
            continue
        names[pkg_dir.name] = cls.name
    return names


def test_every_skill_name_is_unique():
    names = _skill_names()
    inverse: dict[str, list[str]] = {}
    for pkg, nm in names.items():
        inverse.setdefault(nm, []).append(pkg)
    dupes = {nm: pkgs for nm, pkgs in inverse.items() if len(pkgs) > 1}
    assert not dupes, f"Duplicate Skill names: {dupes}"


def test_no_skill_name_collides_with_hull_reserved_keys():
    names = _skill_names()
    clashes = {pkg: nm for pkg, nm in names.items() if nm in _HULL_RESERVED}
    assert not clashes, f"Skill name(s) collide with Hull-reserved ns keys: {clashes}"
