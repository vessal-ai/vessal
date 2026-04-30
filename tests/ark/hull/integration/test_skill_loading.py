"""test_skill_loading — SkillLoader + builtins integration tests."""
import sys
from pathlib import Path

import pytest

from vessal.ark.shell.hull.skill_loader import SkillLoader
from vessal.skills._base import BaseSkill


@pytest.fixture
def skill_env(tmp_path, monkeypatch):
    """Create a skills package with a test_skill for testing."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "__init__.py").write_text("", encoding="utf-8")
    skill_dir = skills_dir / "test_skill"
    skill_dir.mkdir()
    (skill_dir / "__init__.py").write_text(
        "from .skill import TestSkill\n__all__ = ['TestSkill']\n"
    )
    (skill_dir / "skill.py").write_text(
        "from vessal.skills._base import BaseSkill\n"
        "class TestSkill(BaseSkill):\n"
        "    name = 'test_skill'\n"
        "    description = 'Test skill.'\n"
        "    def hello(self): return 'world'\n"
        "    def signal_update(self): self.signal = {'test_skill': 'test_signal'}\n"
    )
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test_skill\ndescription: Test skill.\n---\nTest guide body.\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("skills", None)
    return tmp_path


def test_load_returns_skillbase_subclass(skill_env):
    sm = SkillLoader()
    cls = sm.load("test_skill")
    assert issubclass(cls, BaseSkill)


def test_load_sets_guide(skill_env):
    sm = SkillLoader()
    cls = sm.load("test_skill")
    assert "Test guide body." in cls.guide


def test_instance_signal_update(skill_env):
    sm = SkillLoader()
    cls = sm.load("test_skill")
    instance = cls()
    instance.signal_update()
    assert isinstance(instance.signal, dict)


def test_list_skills(skill_env):
    sm = SkillLoader()
    result = sm.list()
    assert any(s["name"] == "test_skill" for s in result)


def test_unload_cleans_sys_modules(skill_env):
    sm = SkillLoader()
    sm.load("test_skill")
    assert "skills.test_skill" in sys.modules
    sm.unload("test_skill")
    assert "skills.test_skill" not in sys.modules


def test_load_not_found(skill_env):
    sm = SkillLoader()
    with pytest.raises(RuntimeError, match="not found"):
        sm.load("nonexistent")


def test_isinstance_scan_integration(skill_env):
    """End-to-end: load class → instantiate → signal_update called → signal stored."""
    sm = SkillLoader()
    cls = sm.load("test_skill")
    instance = cls()
    instance.signal_update()
    assert "test_skill" in instance.signal
