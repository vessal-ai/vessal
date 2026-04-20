"""test_skill_loading — SkillLoader + builtins integration tests."""
import sys
from pathlib import Path

import pytest

from vessal.ark.shell.hull.skill_loader import SkillLoader
from vessal.ark.shell.hull.skill import SkillBase


@pytest.fixture
def skill_env(tmp_path):
    """Create a skill package for testing."""
    skill_dir = tmp_path / "test_skill"
    skill_dir.mkdir()
    (skill_dir / "__init__.py").write_text(
        "from .skill import TestSkill as Skill\n__all__ = ['Skill']\n"
    )
    (skill_dir / "skill.py").write_text(
        "from vessal.ark.shell.hull.skill import SkillBase\n"
        "class TestSkill(SkillBase):\n"
        "    name = 'test_skill'\n"
        "    description = 'Test skill.'\n"
        "    def hello(self): return 'world'\n"
        "    def _signal(self):\n"
        "        return ('test_skill', 'test_signal')\n"
    )
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test_skill\ndescription: Test skill.\n---\nTest guide body.\n"
    )
    return tmp_path


def test_load_returns_skillbase_subclass(skill_env):
    sm = SkillLoader(skill_paths=[str(skill_env)])
    cls = sm.load("test_skill")
    assert issubclass(cls, SkillBase)


def test_load_sets_guide(skill_env):
    sm = SkillLoader(skill_paths=[str(skill_env)])
    cls = sm.load("test_skill")
    assert "Test guide body." in cls.guide


def test_instance_signal(skill_env):
    sm = SkillLoader(skill_paths=[str(skill_env)])
    cls = sm.load("test_skill")
    instance = cls()
    result = instance._signal()
    assert result == ("test_skill", "test_signal")


def test_list_skills(skill_env):
    sm = SkillLoader(skill_paths=[str(skill_env)])
    result = sm.list()
    assert any(s["name"] == "test_skill" for s in result)


def test_unload_cleans_sys_modules(skill_env):
    sm = SkillLoader(skill_paths=[str(skill_env)])
    sm.load("test_skill")
    assert "test_skill" in sys.modules
    sm.unload("test_skill")
    assert "test_skill" not in sys.modules


def test_load_not_found():
    sm = SkillLoader(skill_paths=[])
    with pytest.raises(RuntimeError, match="not found"):
        sm.load("nonexistent")


def test_isinstance_scan_integration(skill_env):
    """End-to-end: load class → instantiate → kernel scans → signal collected."""
    from vessal.ark.shell.hull.cell.kernel.kernel import Kernel

    sm = SkillLoader(skill_paths=[str(skill_env)])
    cls = sm.load("test_skill")
    k = Kernel()
    k.ns["ts"] = cls()
    k.update_signals()
    outputs = k.ns["_signal_outputs"]
    assert any("test_signal" in body for _, body in outputs)
