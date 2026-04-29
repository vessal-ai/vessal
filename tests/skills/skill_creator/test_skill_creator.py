"""test_skill_creator — skill_creator Skill unit tests.

skill_creator delegates to ark.shell.cli.write_skill_scaffold; these tests cover the Skill's
own responsibilities (target dir resolution, duplicate rejection). Scaffold layout is asserted
against the shared helper.
"""
import pytest


@pytest.fixture
def creator(tmp_path, monkeypatch):
    """Create a skill_creator instance with the target dir redirected to a temp directory."""
    import vessal.skills.skill_creator.skill as sc_module
    monkeypatch.setattr(sc_module, "__file__", str(tmp_path / "skills" / "skill_creator" / "skill.py"))
    from vessal.skills.skill_creator.skill import SkillCreator
    return SkillCreator()


@pytest.fixture
def skills_dir(tmp_path):
    """The target directory that creator resolves to (parent.parent of the monkeypatched __file__)."""
    return tmp_path / "skills"


def test_create_generates_directory(creator, skills_dir):
    result = creator.create("code_review")
    skill_dir = skills_dir / "code_review"
    assert skill_dir.is_dir()
    assert "Created" in result


def test_create_generates_shared_scaffold_files(creator, skills_dir):
    creator.create("code_review")
    d = skills_dir / "code_review"
    assert (d / "__init__.py").exists()
    assert (d / "skill.py").exists()
    assert (d / "SKILL.md").exists()
    assert (d / "requirements.txt").exists()
    assert (d / "tests" / "__init__.py").exists()
    assert (d / "tests" / "test_code_review.py").exists()


def test_create_class_name_camelcase(creator, skills_dir):
    creator.create("my_cool_tool")
    content = (skills_dir / "my_cool_tool" / "skill.py").read_text()
    assert "class MyCoolTool(BaseSkill)" in content


def test_create_init_exports_skill(creator, skills_dir):
    creator.create("code_review")
    init_content = (skills_dir / "code_review" / "__init__.py").read_text()
    assert "from .skill import" in init_content
    assert "as Skill" in init_content


def test_create_duplicate_fails(creator, skills_dir):
    creator.create("code_review")
    result = creator.create("code_review")
    assert "already exists" in result


def test_matches_cli_scaffolder_output(tmp_path, monkeypatch):
    """skill_creator.create and `vessal skill create` write the same file set — R1 invariant."""
    import vessal.skills.skill_creator.skill as sc_module
    monkeypatch.setattr(sc_module, "__file__", str(tmp_path / "skills" / "skill_creator" / "skill.py"))

    from vessal.skills.skill_creator.skill import SkillCreator
    from vessal.ark.shell.cli.scaffold import write_skill_scaffold

    skill_dir = tmp_path / "skills" / "demo"
    cli_dir = tmp_path / "cli" / "demo"

    sc = SkillCreator()
    sc.create("demo")
    write_skill_scaffold(cli_dir, "demo")

    rel = lambda root: sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    assert rel(skill_dir) == rel(cli_dir)
    assert (skill_dir / "skill.py").read_text() == (cli_dir / "skill.py").read_text()
    assert (skill_dir / "SKILL.md").read_text() == (cli_dir / "SKILL.md").read_text()
