# src/vessal/ark/shell/hub/tests/test_installer.py
"""Tests for skill installer."""
from pathlib import Path

import pytest

from vessal.ark.shell.hull.hub.installer import locate_skill_in_repo, copy_skill


def _make_single_skill(repo_dir: Path, name: str = "my_skill") -> None:
    """Create a single-skill repo layout at repo_dir root."""
    (repo_dir / "__init__.py").write_text(f"from .skill import Sk as Skill\n")
    (repo_dir / "skill.py").write_text(
        f"from vessal.ark.shell.hull.skill import SkillBase\n\n"
        f"class Sk(SkillBase):\n"
        f"    name = '{name}'\n"
        f"    description = 'test'\n"
    )
    (repo_dir / "SKILL.md").write_text(
        f"---\nname: {name}\nversion: \"1.0.0\"\ndescription: test\n---\n\nGuide."
    )


def _make_monorepo(repo_dir: Path) -> None:
    """Create a monorepo layout with skills/ subdirectory."""
    skills = repo_dir / "skills"
    for name in ("alpha", "beta"):
        d = skills / name
        d.mkdir(parents=True)
        _make_single_skill(d, name)


def test_locate_single_skill(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_single_skill(repo)
    result = locate_skill_in_repo(repo, subpath=None)
    assert result == repo


def test_locate_monorepo_scan(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_monorepo(repo)
    # No subpath and no root SKILL.md → scan skills/
    results = locate_skill_in_repo(repo, subpath=None)
    # Returns the skills/ parent for monorepo (caller picks by name)
    assert results == repo / "skills"


def test_locate_monorepo_with_subpath(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_monorepo(repo)
    result = locate_skill_in_repo(repo, subpath="skills/alpha")
    assert result == repo / "skills" / "alpha"
    assert (result / "SKILL.md").exists()


def test_locate_subpath_not_found(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _make_monorepo(repo)
    with pytest.raises(RuntimeError, match="not found"):
        locate_skill_in_repo(repo, subpath="skills/nonexistent")


def test_copy_skill(tmp_path: Path):
    # Set up source
    source = tmp_path / "source" / "my_skill"
    source.mkdir(parents=True)
    _make_single_skill(source)

    # Copy to target
    target_base = tmp_path / "target"
    target_base.mkdir()
    copy_skill(source, target_base, "my_skill")

    dest = target_base / "my_skill"
    assert dest.is_dir()
    assert (dest / "SKILL.md").exists()
    assert (dest / "skill.py").exists()
    assert (dest / "__init__.py").exists()


def test_copy_skill_overwrites_existing(tmp_path: Path):
    source = tmp_path / "source" / "sk"
    source.mkdir(parents=True)
    _make_single_skill(source, "sk")

    target_base = tmp_path / "target"
    (target_base / "sk").mkdir(parents=True)
    (target_base / "sk" / "old_file.txt").write_text("old")

    copy_skill(source, target_base, "sk")
    assert not (target_base / "sk" / "old_file.txt").exists()
    assert (target_base / "sk" / "SKILL.md").exists()
