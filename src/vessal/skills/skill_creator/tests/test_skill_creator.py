"""test_skill_creator — skill_creator Skill unit tests.

skill_creator delegates to ark.shell.cli.write_skill_scaffold; these tests cover the Skill's
own responsibilities (skill_paths resolution, duplicate rejection, description propagation).
Scaffold layout is asserted against the shared helper.
"""
import pytest
from pathlib import Path


@pytest.fixture
def creator(tmp_path):
    """Create a skill_creator instance with skill_paths pointing to a temp directory."""
    from vessal.skills.skill_creator.skill import SkillCreator
    ns = {"skill_paths": [str(tmp_path)]}
    return SkillCreator(ns=ns)


def test_create_generates_directory(creator, tmp_path):
    result = creator.create("code_review", "code review tool")
    skill_dir = tmp_path / "code_review"
    assert skill_dir.is_dir()
    assert "Created" in result


def test_create_generates_shared_scaffold_files(creator, tmp_path):
    creator.create("code_review", "code review tool")
    d = tmp_path / "code_review"
    assert (d / "__init__.py").exists()
    assert (d / "skill.py").exists()
    assert (d / "SKILL.md").exists()
    assert (d / "requirements.txt").exists()
    assert (d / "tests" / "__init__.py").exists()
    assert (d / "tests" / "test_code_review.py").exists()


def test_create_writes_user_description(creator, tmp_path):
    """description arg is propagated into skill.py and SKILL.md frontmatter."""
    creator.create("code_review", "code review tool")
    skill_py = (tmp_path / "code_review" / "skill.py").read_text()
    skill_md = (tmp_path / "code_review" / "SKILL.md").read_text()
    assert 'description = "code review tool"' in skill_py
    assert 'description: "code review tool"' in skill_md


def test_create_class_name_camelcase(creator, tmp_path):
    creator.create("my_cool_tool", "cool tool")
    content = (tmp_path / "my_cool_tool" / "skill.py").read_text()
    assert "class MyCoolTool(SkillBase)" in content


def test_create_init_exports_skill(creator, tmp_path):
    creator.create("code_review", "code review tool")
    init_content = (tmp_path / "code_review" / "__init__.py").read_text()
    assert "from .skill import" in init_content
    assert "as Skill" in init_content


def test_create_duplicate_fails(creator, tmp_path):
    creator.create("code_review", "code review tool")
    result = creator.create("code_review", "another one")
    assert "already exists" in result


def test_create_no_skill_paths():
    from vessal.skills.skill_creator.skill import SkillCreator
    c = SkillCreator(ns={})
    result = c.create("test", "test")
    assert "failed" in result.lower() or "skill_paths" in result


def test_matches_cli_scaffolder_output(tmp_path):
    """skill_creator.create and `vessal skill init` write the same file set — R1 invariant."""
    from vessal.skills.skill_creator.skill import SkillCreator
    from vessal.ark.shell.cli import write_skill_scaffold

    skill_dir = tmp_path / "demo"
    cli_dir = tmp_path / "cli" / "demo"

    SkillCreator(ns={"skill_paths": [str(tmp_path)]}).create("demo", "demo tool")
    write_skill_scaffold(cli_dir, "demo", "demo tool")

    rel = lambda root: sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    assert rel(skill_dir) == rel(cli_dir)
    assert (skill_dir / "skill.py").read_text() == (cli_dir / "skill.py").read_text()
    assert (skill_dir / "SKILL.md").read_text() == (cli_dir / "SKILL.md").read_text()
