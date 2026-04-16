"""test_skill_manager — SkillManager lifecycle tests."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from vessal.ark.shell.hull.skill_manager import SkillManager


@pytest.fixture
def tmp_skill(tmp_path):
    """Create a minimal skill package in tmp_path."""
    skill_dir = tmp_path / "dummy"
    skill_dir.mkdir()
    (skill_dir / "__init__.py").write_text(
        "from .skill import Dummy as Skill\n"
    )
    (skill_dir / "skill.py").write_text(
        "from vessal.ark.shell.hull.skill import SkillBase\n"
        "class Dummy(SkillBase):\n"
        "    name = 'dummy'\n"
        "    description = 'A dummy skill.'\n"
    )
    (skill_dir / "SKILL.md").write_text(
        "---\nname: dummy\ndescription: A dummy skill.\n---\nDummy guide body.\n"
    )
    return tmp_path


def test_list_skills(tmp_skill):
    sm = SkillManager(skill_paths=[str(tmp_skill)])
    result = sm.list()
    assert len(result) == 1
    assert result[0]["name"] == "dummy"
    assert result[0]["description"] == "A dummy skill."


def test_load_returns_class(tmp_skill):
    sm = SkillManager(skill_paths=[str(tmp_skill)])
    cls = sm.load("dummy")
    from vessal.ark.shell.hull.skill import SkillBase
    assert issubclass(cls, SkillBase)
    assert cls.name == "dummy"
    assert cls.guide == "Dummy guide body."


def test_load_sets_guide_from_skill_md(tmp_skill):
    sm = SkillManager(skill_paths=[str(tmp_skill)])
    cls = sm.load("dummy")
    assert "Dummy guide body." in cls.guide


def test_load_not_found():
    sm = SkillManager(skill_paths=[])
    with pytest.raises(RuntimeError, match="not found"):
        sm.load("nonexistent")


def test_unload_cleans_sys_modules(tmp_skill):
    sm = SkillManager(skill_paths=[str(tmp_skill)])
    sm.load("dummy")
    assert "dummy" in sys.modules
    sm.unload("dummy")
    assert "dummy" not in sys.modules


def test_load_installs_deps(tmp_skill):
    """load() calls install when requirements.txt exists."""
    req = tmp_skill / "dummy" / "requirements.txt"
    req.write_text("some-fake-package\n")
    sm = SkillManager(skill_paths=[str(tmp_skill)])
    with patch("vessal.ark.shell.hull.skill_manager._install_packages") as mock_install:
        sm.load("dummy")
        mock_install.assert_called_once_with(["some-fake-package"])


def test_loaded_names_tracks_loaded(tmp_skill):
    sm = SkillManager(skill_paths=[str(tmp_skill)])
    assert sm.loaded_names == []
    sm.load("dummy")
    assert "dummy" in sm.loaded_names
    sm.unload("dummy")
    assert sm.loaded_names == []
