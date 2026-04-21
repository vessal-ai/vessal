"""test_skill_scaffold_boot — vessal scaffold produces a Skill that Hull can load."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from vessal.ark.shell.cli.scaffold import write_skill_scaffold


@pytest.fixture
def hull_from_scaffold(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.chdir(tmp_path)

    skill_name = "smoketest"
    skills_dir = tmp_path / "skills" / "local"
    skill_pkg = skills_dir / skill_name
    skill_pkg.mkdir(parents=True)
    write_skill_scaffold(skill_pkg, skill_name, "smoke placeholder")

    (tmp_path / "hull.toml").write_text(
        f'[hull]\n'
        f'skills = ["{skill_name}"]\n'
        f'skill_paths = ["skills/local"]\n',
        encoding="utf-8",
    )

    sys.modules.pop(skill_name, None)

    from vessal.ark.shell.hull.hull import Hull
    hull = Hull(str(tmp_path))
    yield hull, skill_name

    sys.modules.pop(skill_name, None)


def test_scaffold_module_imports(tmp_path):
    skill_name = "demo_import"
    skill_pkg = tmp_path / skill_name
    skill_pkg.mkdir()
    write_skill_scaffold(skill_pkg, skill_name, "demo")

    sys.path.insert(0, str(tmp_path))
    try:
        sys.modules.pop(skill_name, None)
        mod = importlib.import_module(skill_name)
        assert hasattr(mod, "Skill")
        from vessal.ark.shell.hull.skill import SkillBase
        assert issubclass(mod.Skill, SkillBase)
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop(skill_name, None)


def test_hull_loads_scaffolded_skill(hull_from_scaffold):
    hull, skill_name = hull_from_scaffold
    assert skill_name in hull._cell.ns
    instance = hull._cell.ns[skill_name]
    assert instance._signal() is None or isinstance(instance._signal(), tuple)
    assert instance._prompt() is None or isinstance(instance._prompt(), tuple)


def test_scaffolded_skill_accepts_ns_kwarg(tmp_path):
    import inspect
    skill_name = "demo_sig"
    skill_pkg = tmp_path / skill_name
    skill_pkg.mkdir()
    write_skill_scaffold(skill_pkg, skill_name, "demo")

    sys.path.insert(0, str(tmp_path))
    try:
        sys.modules.pop(skill_name, None)
        mod = importlib.import_module(skill_name)
        sig = inspect.signature(mod.Skill.__init__)
        assert "ns" in sig.parameters, f"expected ns parameter in scaffold __init__: {sig}"
        assert sig.parameters["ns"].default is None
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop(skill_name, None)
