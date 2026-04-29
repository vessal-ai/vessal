"""test_skill_scaffold_boot — vessal scaffold produces a Skill that Hull can load."""
from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

import pytest

from vessal.ark.shell.cli.scaffold import write_skill_scaffold

_VESSAL_SKILLS_SRC = Path(__file__).resolve().parents[2] / "src" / "vessal" / "skills"


@pytest.fixture
def hull_from_scaffold(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.chdir(tmp_path)

    skill_name = "smoketest"
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "__init__.py").write_text("", encoding="utf-8")

    # Copy built-in skills required by Hull boot script into the project skills/ dir.
    for builtin in ("system", "compaction"):
        shutil.copytree(
            str(_VESSAL_SKILLS_SRC / builtin),
            str(skills_dir / builtin),
            ignore=shutil.ignore_patterns("__pycache__"),
        )

    skill_pkg = skills_dir / skill_name
    skill_pkg.mkdir(parents=True)
    write_skill_scaffold(skill_pkg, skill_name)

    (tmp_path / "hull.toml").write_text(
        f'[hull]\n'
        f'skills = ["{skill_name}"]\n',
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    for mod in list(sys.modules):
        if mod == "skills" or mod.startswith("skills."):
            sys.modules.pop(mod, None)

    from vessal.ark.shell.hull.hull import Hull
    hull = Hull(str(tmp_path))
    yield hull, skill_name

    for mod in list(sys.modules):
        if mod == "skills" or mod.startswith("skills."):
            sys.modules.pop(mod, None)


def test_scaffold_module_imports(tmp_path):
    skill_name = "demo_import"
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "__init__.py").write_text("", encoding="utf-8")
    skill_pkg = skills_dir / skill_name
    skill_pkg.mkdir()
    write_skill_scaffold(skill_pkg, skill_name)

    sys.path.insert(0, str(tmp_path))
    try:
        sys.modules.pop("skills", None)
        sys.modules.pop(f"skills.{skill_name}", None)
        mod = importlib.import_module(f"skills.{skill_name}")
        assert hasattr(mod, "Skill")
        from vessal.skills._base import BaseSkill
        assert issubclass(mod.Skill, BaseSkill)
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("skills", None)
        sys.modules.pop(f"skills.{skill_name}", None)


def test_hull_loads_scaffolded_skill(hull_from_scaffold):
    hull, skill_name = hull_from_scaffold
    # Skills are instantiated by boot_script in G (exec(boot_script, G, G)).
    assert skill_name in hull._main_cell.G
    instance = hull._main_cell.G[skill_name]
    instance.signal_update()
    assert isinstance(instance.signal, dict)
    assert instance._prompt() is None or isinstance(instance._prompt(), tuple)


def test_scaffolded_skill_accepts_ns_kwarg(tmp_path):
    import inspect
    skill_name = "demo_sig"
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "__init__.py").write_text("", encoding="utf-8")
    skill_pkg = skills_dir / skill_name
    skill_pkg.mkdir()
    write_skill_scaffold(skill_pkg, skill_name)

    sys.path.insert(0, str(tmp_path))
    try:
        sys.modules.pop("skills", None)
        sys.modules.pop(f"skills.{skill_name}", None)
        mod = importlib.import_module(f"skills.{skill_name}")
        sig = inspect.signature(mod.Skill.__init__)
        assert "ns" in sig.parameters, f"expected ns parameter in scaffold __init__: {sig}"
        assert sig.parameters["ns"].default is None
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("skills", None)
        sys.modules.pop(f"skills.{skill_name}", None)
