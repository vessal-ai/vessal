"""test_skill_loader — SkillLoader lifecycle tests."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from vessal.ark.shell.hull.skill_loader import SkillLoader


@pytest.fixture
def tmp_skill(tmp_path):
    """Create a minimal skill package in tmp_path."""
    skill_dir = tmp_path / "dummy"
    skill_dir.mkdir()
    (skill_dir / "__init__.py").write_text(
        "from .skill import Dummy as Skill\n"
    )
    (skill_dir / "skill.py").write_text(
        "from vessal.skills._base import BaseSkill\n"
        "class Dummy(BaseSkill):\n"
        "    name = 'dummy'\n"
        "    description = 'A dummy skill.'\n"
    )
    (skill_dir / "SKILL.md").write_text(
        "---\nname: dummy\ndescription: A dummy skill.\n---\nDummy guide body.\n"
    )
    return tmp_path


def test_list_skills(tmp_skill):
    sm = SkillLoader(skill_paths=[str(tmp_skill)])
    result = sm.list()
    assert len(result) == 1
    assert result[0]["name"] == "dummy"
    assert result[0]["description"] == "A dummy skill."


def test_load_returns_class(tmp_skill):
    sm = SkillLoader(skill_paths=[str(tmp_skill)])
    cls = sm.load("dummy")
    from vessal.skills._base import BaseSkill
    assert issubclass(cls, BaseSkill)
    assert cls.name == "dummy"
    assert cls.guide == "Dummy guide body."


def test_load_sets_guide_from_skill_md(tmp_skill):
    sm = SkillLoader(skill_paths=[str(tmp_skill)])
    cls = sm.load("dummy")
    assert "Dummy guide body." in cls.guide


def test_load_not_found():
    sm = SkillLoader(skill_paths=[])
    with pytest.raises(RuntimeError, match="not found"):
        sm.load("nonexistent")


def test_unload_cleans_sys_modules(tmp_skill):
    sm = SkillLoader(skill_paths=[str(tmp_skill)])
    sm.load("dummy")
    assert "dummy" in sys.modules
    sm.unload("dummy")
    assert "dummy" not in sys.modules


def test_load_installs_deps(tmp_skill):
    """load() calls install when requirements.txt exists."""
    req = tmp_skill / "dummy" / "requirements.txt"
    req.write_text("some-fake-package\n")
    sm = SkillLoader(skill_paths=[str(tmp_skill)])
    with patch("vessal.ark.shell.hull.skill_loader._install_packages") as mock_install:
        sm.load("dummy")
        mock_install.assert_called_once_with(["some-fake-package"])


def test_loaded_names_tracks_loaded(tmp_skill):
    sm = SkillLoader(skill_paths=[str(tmp_skill)])
    assert sm.loaded_names == []
    sm.load("dummy")
    assert "dummy" in sm.loaded_names
    sm.unload("dummy")
    assert sm.loaded_names == []


# ---------------------------------------------------------------------------
# _parse_skill_md unit tests
# ---------------------------------------------------------------------------
from vessal.ark.shell.hull.skill_loader import _parse_skill_md  # noqa: E402


def test_parse_v0_format(tmp_path: Path):
    """Existing v0 format still works."""
    md = tmp_path / "SKILL.md"
    md.write_text(
        "---\nname: tasks\ndescription: Hierarchical task management\n---\n\n# tasks\n\nBody text."
    )
    meta, body = _parse_skill_md(md)
    assert meta["name"] == "tasks"
    assert meta["description"] == "Hierarchical task management"
    assert "Body text." in body


def test_parse_v1_format(tmp_path: Path):
    """v1 format with version, author, license, requires."""
    md = tmp_path / "SKILL.md"
    md.write_text(
        '---\n'
        'name: browser\n'
        'version: "1.0.0"\n'
        'description: "web page browsing"\n'
        'author: "vessal-ai"\n'
        'license: "Apache-2.0"\n'
        'requires:\n'
        '  skills: [tasks, memory]\n'
        '  python: ">=3.12"\n'
        '---\n'
        '\n'
        '# browser\n'
        '\nBrowse the web.'
    )
    meta, body = _parse_skill_md(md)
    assert meta["name"] == "browser"
    assert meta["version"] == "1.0.0"
    assert meta["author"] == "vessal-ai"
    assert meta["license"] == "Apache-2.0"
    assert meta["requires"] == {"skills": ["tasks", "memory"], "python": ">=3.12"}
    assert "Browse the web." in body


def test_parse_v1_empty_requires(tmp_path: Path):
    """v1 format with empty requires.skills list."""
    md = tmp_path / "SKILL.md"
    md.write_text(
        '---\n'
        'name: pin\n'
        'version: "1.0.0"\n'
        'description: "pin variables"\n'
        'requires:\n'
        '  skills: []\n'
        '---\n'
        '\n'
        'Body.'
    )
    meta, body = _parse_skill_md(md)
    assert meta["requires"] == {"skills": []}
    assert "Body." in body


def test_parse_missing_file(tmp_path: Path):
    """Non-existent file returns empty."""
    meta, body = _parse_skill_md(tmp_path / "nope.md")
    assert meta == {}
    assert body == ""


def test_parse_no_frontmatter(tmp_path: Path):
    """File without frontmatter returns body only."""
    md = tmp_path / "SKILL.md"
    md.write_text("# Just a guide\n\nNo frontmatter here.")
    meta, body = _parse_skill_md(md)
    assert meta == {}
    assert "No frontmatter here." in body


# ---------------------------------------------------------------------------
# requires.skills dependency checking tests
# ---------------------------------------------------------------------------

def _make_skill_dir(base: Path, name: str, requires_skills: list[str] | None = None) -> Path:
    """Create a minimal valid skill directory."""
    skill_dir = base / name
    skill_dir.mkdir()

    class_name = "".join(part.capitalize() for part in name.split("_"))

    (skill_dir / "__init__.py").write_text(
        f"from .skill import {class_name} as Skill\n"
    )
    (skill_dir / "skill.py").write_text(
        f"from vessal.skills._base import BaseSkill\n\n"
        f"class {class_name}(BaseSkill):\n"
        f"    name = '{name}'\n"
        f"    description = 'test skill'\n"
    )

    requires_block = ""
    if requires_skills is not None:
        skills_str = ", ".join(requires_skills)
        requires_block = f"requires:\n  skills: [{skills_str}]\n"

    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\nversion: \"1.0.0\"\ndescription: test\n{requires_block}---\n\nGuide."
    )
    return skill_dir


def test_load_skill_with_satisfied_deps(tmp_path: Path):
    """Loading a skill whose requires.skills are all loaded succeeds."""
    from vessal.ark.shell.hull.skill_loader import SkillLoader

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _make_skill_dir(skills_dir, "dep_a")
    _make_skill_dir(skills_dir, "dep_b", requires_skills=["dep_a"])

    mgr = SkillLoader(skill_paths=[str(skills_dir)])
    mgr.load("dep_a")
    cls = mgr.load("dep_b")
    assert cls.name == "dep_b"


def test_load_skill_with_missing_deps(tmp_path: Path):
    """Loading a skill with unsatisfied requires.skills raises RuntimeError."""
    from vessal.ark.shell.hull.skill_loader import SkillLoader

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _make_skill_dir(skills_dir, "lonely", requires_skills=["nonexistent"])

    mgr = SkillLoader(skill_paths=[str(skills_dir)])
    with pytest.raises(RuntimeError, match="requires skill 'nonexistent'"):
        mgr.load("lonely")


def test_load_skill_without_requires(tmp_path: Path):
    """Loading a skill without requires block succeeds (backward compat)."""
    from vessal.ark.shell.hull.skill_loader import SkillLoader

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    _make_skill_dir(skills_dir, "simple")

    mgr = SkillLoader(skill_paths=[str(skills_dir)])
    cls = mgr.load("simple")
    assert cls.name == "simple"
