"""test_skill_creator — skill_creator Skill unit tests."""
import pytest
from pathlib import Path


@pytest.fixture
def creator(tmp_path):
    """Create a skill_creator instance with skill_paths pointing to a temp directory."""
    from vessal.skills.skill_creator.skill import SkillCreator
    ns = {"skill_paths": [str(tmp_path)]}
    return SkillCreator(ns=ns)


def test_create_generates_directory(creator, tmp_path):
    """create() generates the correct directory structure under skill_paths[0]."""
    result = creator.create("code_review", "code review tool")
    skill_dir = tmp_path / "code_review"
    assert skill_dir.is_dir()
    assert (skill_dir / "__init__.py").exists()
    assert (skill_dir / "skill.py").exists()
    assert (skill_dir / "SKILL.md").exists()
    assert "Created" in result


def test_create_init_exports_skill(creator, tmp_path):
    """__init__.py exports the Skill class."""
    creator.create("code_review", "code review tool")
    init_content = (tmp_path / "code_review" / "__init__.py").read_text()
    assert "from .skill import" in init_content
    assert "as Skill" in init_content


def test_create_skill_py_has_correct_class(creator, tmp_path):
    """skill.py contains the correct SkillBase subclass."""
    creator.create("code_review", "code review tool")
    skill_content = (tmp_path / "code_review" / "skill.py").read_text()
    assert "class CodeReview(SkillBase)" in skill_content
    assert 'name = "code_review"' in skill_content
    assert 'description = "code review tool"' in skill_content


def test_create_skill_py_has_protocol_comments(creator, tmp_path):
    """skill.py contains protocol spec comments."""
    creator.create("code_review", "code review tool")
    skill_content = (tmp_path / "code_review" / "skill.py").read_text()
    assert "≤15" in skill_content or "description ≤ 15" in skill_content
    assert "_signal()" in skill_content
    assert "method signatures" in skill_content or "method names" in skill_content


def test_create_skill_md_has_frontmatter(creator, tmp_path):
    """SKILL.md has correct frontmatter."""
    creator.create("code_review", "code review tool")
    md_content = (tmp_path / "code_review" / "SKILL.md").read_text()
    assert "name: code_review" in md_content
    assert "description:" in md_content


def test_create_duplicate_fails(creator, tmp_path):
    """Creating a Skill with a duplicate name returns an error."""
    creator.create("code_review", "code review tool")
    result = creator.create("code_review", "another one")
    assert "already exists" in result


def test_create_no_skill_paths():
    """Creation fails when skill_paths is empty."""
    from vessal.skills.skill_creator.skill import SkillCreator
    c = SkillCreator(ns={})
    result = c.create("test", "test")
    assert "failed" in result.lower() or "skill_paths" in result


def test_create_class_name_camelcase(creator, tmp_path):
    """Underscore names are correctly converted to CamelCase class names."""
    creator.create("my_cool_tool", "cool tool")
    content = (tmp_path / "my_cool_tool" / "skill.py").read_text()
    assert "class MyCoolTool(SkillBase)" in content


def test_create_generates_context_md(creator, tmp_path):
    """create() generates a CONTEXT.md boundary contract framework."""
    creator.create("code_review", "code review tool")
    path = tmp_path / "code_review" / "CONTEXT.md"
    assert path.exists()
    content = path.read_text()
    assert "# Code Review" in content or "# code_review" in content
    assert "Responsible for" in content
    assert "Not responsible for" in content
    assert "Constraints" in content
    assert "Design" in content
    assert "Status" in content


def test_create_generates_tests_directory(creator, tmp_path):
    """create() generates a tests/ directory, __init__.py, and test scaffold."""
    creator.create("code_review", "code review tool")
    tests_dir = tmp_path / "code_review" / "tests"
    assert tests_dir.is_dir()
    assert (tests_dir / "__init__.py").exists()
    test_file = tests_dir / "test_code_review.py"
    assert test_file.exists()
    content = test_file.read_text()
    assert "import pytest" in content
    assert "CodeReview" in content or "code_review" in content
    assert "def test_" in content


def test_create_skill_py_has_ns_init(creator, tmp_path):
    """skill.py template includes ns parameter and _data_dir retrieval example."""
    creator.create("code_review", "code review tool")
    content = (tmp_path / "code_review" / "skill.py").read_text()
    assert "ns: dict | None = None" in content
    assert "_data_dir" in content
    assert "Three-layer" in content or "_prompt" in content
    assert "guide" in content
    assert "_signal" in content


def test_create_skill_py_has_complete_protocol(creator, tmp_path):
    """skill.py template contains complete overridable method documentation."""
    creator.create("code_review", "code review tool")
    content = (tmp_path / "code_review" / "skill.py").read_text()
    assert "_signal()" in content
    assert "_prompt()" in content
    assert "guide" in content
    assert "ns" in content


def test_create_skill_md_has_guide_template(creator, tmp_path):
    """SKILL.md contains a complete guide template and format spec."""
    creator.create("code_review", "code review tool")
    content = (tmp_path / "code_review" / "SKILL.md").read_text()
    assert "## Methods" in content
    assert "## Usage" in content
    assert "name.method(arg)" in content or "code_review." in content


def test_create_generates_reference_md(creator, tmp_path):
    """create() generates REFERENCE.md containing SkillBase docstring and example source."""
    creator.create("code_review", "code review tool")
    path = tmp_path / "code_review" / "REFERENCE.md"
    assert path.exists()
    content = path.read_text()
    assert "SkillBase" in content
    assert "name: str" in content or "description: str" in content
    assert "class Pin" in content
    assert "class Memory" in content
    assert "Dual-sided interface" in content or "dual-sided" in content.lower()


def test_create_generates_all_files(creator, tmp_path):
    """create() generates the complete 7-file directory structure."""
    creator.create("code_review", "code review tool")
    d = tmp_path / "code_review"
    assert (d / "__init__.py").exists()
    assert (d / "skill.py").exists()
    assert (d / "SKILL.md").exists()
    assert (d / "CONTEXT.md").exists()
    assert (d / "REFERENCE.md").exists()
    assert (d / "tests" / "__init__.py").exists()
    assert (d / "tests" / "test_code_review.py").exists()
