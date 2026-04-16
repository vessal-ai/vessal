"""test_skill_interface — Every built-in Skill inherits SkillBase and has SKILL.md."""
from pathlib import Path

from vessal.ark.shell.hull.skill import SkillBase

_SKILLS_DIR = Path(__file__).resolve().parents[2] / "src/vessal/skills"


def _iter_skill_packages():
    for pkg_dir in sorted(_SKILLS_DIR.iterdir()):
        if pkg_dir.is_dir() and (pkg_dir / "__init__.py").exists():
            yield pkg_dir


def test_all_skills_export_skillbase_subclass():
    """Every skill's __init__.py exports 'Skill' which is a SkillBase subclass."""
    import importlib
    for pkg_dir in _iter_skill_packages():
        mod = importlib.import_module(f"vessal.skills.{pkg_dir.name}")
        cls = getattr(mod, "Skill", None)
        assert cls is not None, f"{pkg_dir.name} does not export Skill"
        assert issubclass(cls, SkillBase), f"{pkg_dir.name}.Skill does not inherit SkillBase"


def test_all_skills_have_skill_md():
    """Every skill has SKILL.md."""
    for pkg_dir in _iter_skill_packages():
        assert (pkg_dir / "SKILL.md").exists(), f"{pkg_dir.name} missing SKILL.md"


def test_all_skills_have_name_and_description():
    """Every skill class defines name and description."""
    import importlib
    for pkg_dir in _iter_skill_packages():
        mod = importlib.import_module(f"vessal.skills.{pkg_dir.name}")
        cls = mod.Skill
        assert isinstance(cls.name, str) and cls.name, f"{pkg_dir.name} missing name"
        assert isinstance(cls.description, str) and cls.description, f"{pkg_dir.name} missing description"
