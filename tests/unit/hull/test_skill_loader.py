"""Unit tests for SkillLoader (post-flat-layout)."""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from vessal.ark.shell.hull.skill_loader import SkillLoader


def _make_skill(skills_dir: Path, name: str, class_name: str = "MySkill", body: str = "") -> None:
    pkg = skills_dir / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        f"from .skill import {class_name} as Skill\n",
        encoding="utf-8",
    )
    (pkg / "skill.py").write_text(
        textwrap.dedent(f"""
            class {class_name}:
                name = {name!r}
                description = "test"
        """),
        encoding="utf-8",
    )
    (pkg / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test\n---\n{body}\n",
        encoding="utf-8",
    )


@pytest.fixture
def project_skills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    # Ensure no stale 'skills' package in sys.modules.
    sys.modules.pop("skills", None)
    return skills_dir


def test_load_returns_skill_class(project_skills: Path):
    _make_skill(project_skills, "mytool")
    loader = SkillLoader()
    cls = loader.load("mytool")
    assert cls.__name__ == "MySkill"


def test_load_missing_skill_raises(project_skills: Path):
    loader = SkillLoader()
    with pytest.raises(RuntimeError, match="not found"):
        loader.load("does_not_exist")


def test_load_without_skill_export_raises(project_skills: Path):
    pkg = project_skills / "broken"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# missing Skill\n", encoding="utf-8")
    (pkg / "SKILL.md").write_text("---\nname: broken\n---\n", encoding="utf-8")
    loader = SkillLoader()
    with pytest.raises(RuntimeError, match="does not export 'Skill'"):
        loader.load("broken")


def test_unload_clears_sys_modules(project_skills: Path):
    _make_skill(project_skills, "mytool")
    loader = SkillLoader()
    loader.load("mytool")
    assert "skills.mytool" in sys.modules
    loader.unload("mytool")
    assert "skills.mytool" not in sys.modules
    assert "mytool" not in loader.loaded_names


def test_skill_dir_returns_path(project_skills: Path):
    _make_skill(project_skills, "mytool")
    loader = SkillLoader()
    loader.load("mytool")
    assert loader.skill_dir("mytool") == str(project_skills / "mytool")


def test_has_server(project_skills: Path):
    _make_skill(project_skills, "withserver")
    (project_skills / "withserver" / "server.py").write_text("# server\n", encoding="utf-8")
    _make_skill(project_skills, "noserver")
    loader = SkillLoader()
    assert loader.has_server("withserver") is True
    assert loader.has_server("noserver") is False


def test_list_reads_skill_md(project_skills: Path):
    _make_skill(project_skills, "alpha")
    _make_skill(project_skills, "beta")
    loader = SkillLoader()
    listed = sorted(loader.list(), key=lambda d: d["name"])
    assert [d["name"] for d in listed] == ["alpha", "beta"]


def test_requires_unmet_raises(project_skills: Path):
    _make_skill(project_skills, "needsdep")
    (project_skills / "needsdep" / "SKILL.md").write_text(
        textwrap.dedent("""\
            ---
            name: needsdep
            description: test
            requires:
              skills: [missing]
            ---
        """),
        encoding="utf-8",
    )
    loader = SkillLoader()
    with pytest.raises(RuntimeError, match="requires 'missing'"):
        loader.load("needsdep")
