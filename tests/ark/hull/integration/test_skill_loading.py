"""test_skill_loading — SkillLoader + builtins integration tests."""
import sys
from pathlib import Path

import pytest

from vessal.ark.shell.hull.skill_loader import SkillLoader
from vessal.skills._base import BaseSkill


@pytest.fixture
def skill_env(tmp_path):
    """Create a skill package for testing."""
    skill_dir = tmp_path / "test_skill"
    skill_dir.mkdir()
    (skill_dir / "__init__.py").write_text(
        "from .skill import TestSkill as Skill\n__all__ = ['Skill']\n"
    )
    (skill_dir / "skill.py").write_text(
        "from vessal.skills._base import BaseSkill\n"
        "class TestSkill(BaseSkill):\n"
        "    name = 'test_skill'\n"
        "    description = 'Test skill.'\n"
        "    def hello(self): return 'world'\n"
        "    def signal_update(self):\n"
        "        self.signal = {'status': 'test_signal'}\n"
    )
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test_skill\ndescription: Test skill.\n---\nTest guide body.\n"
    )
    return tmp_path


def test_load_returns_baseskill_subclass(skill_env):
    sm = SkillLoader(skill_paths=[str(skill_env)])
    cls = sm.load("test_skill")
    assert issubclass(cls, BaseSkill)


def test_load_sets_guide(skill_env):
    sm = SkillLoader(skill_paths=[str(skill_env)])
    cls = sm.load("test_skill")
    assert "Test guide body." in cls.guide


def test_instance_signal(skill_env):
    sm = SkillLoader(skill_paths=[str(skill_env)])
    cls = sm.load("test_skill")
    instance = cls()
    instance.signal_update()
    assert instance.signal == {"status": "test_signal"}


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


def test_isinstance_scan_integration(tmp_path):
    """End-to-end: load BaseSkill subclass → instantiate → kernel scans → signal collected."""
    from vessal.ark.shell.hull.cell.kernel.kernel import Kernel

    # Create a skill using the new BaseSkill contract
    skill_dir = tmp_path / "scan_skill"
    skill_dir.mkdir()
    (skill_dir / "__init__.py").write_text(
        "from .skill import ScanSkill as Skill\n__all__ = ['Skill']\n"
    )
    (skill_dir / "skill.py").write_text(
        "from vessal.skills._base import BaseSkill\n"
        "class ScanSkill(BaseSkill):\n"
        "    name = 'scan_skill'\n"
        "    description = 'Scan skill.'\n"
        "    def signal_update(self):\n"
        "        self.signal = {'status': 'test_signal'}\n"
    )
    (skill_dir / "SKILL.md").write_text("---\nname: scan_skill\ndescription: Scan.\n---\nGuide.\n")

    sm = SkillLoader(skill_paths=[str(tmp_path)])
    cls = sm.load("scan_skill")
    from vessal.ark.shell.hull.cell.kernel.boot import compose_boot_script
    k = Kernel(boot_script=compose_boot_script([]))
    k.L["ts"] = cls()
    k.ping(None, {"globals": k.G, "locals": k.L})
    signals = k.L["signals"]
    assert ("ScanSkill", "ts", "L") in signals
    assert signals[("ScanSkill", "ts", "L")].get("status") == "test_signal"
