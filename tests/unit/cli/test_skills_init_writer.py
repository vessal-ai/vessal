"""Unit tests for the <project>/skills/__init__.py registry helper."""
from __future__ import annotations

from pathlib import Path

from vessal.ark.shell.cli.skills_init_writer import (
    write_initial,
    add as add_skill,
    remove as remove_skill,
)


def test_write_initial_emits_alphabetical_imports(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    write_initial(skills_dir, ["chat", "system", "skill_manager"])
    text = (skills_dir / "__init__.py").read_text(encoding="utf-8")
    expected_imports = [
        "from .chat import Chat",
        "from .skill_manager import SkillManager",
        "from .system import System",
    ]
    for line in expected_imports:
        assert line in text
    assert '__all__ = ["Chat", "SkillManager", "System"]' in text


def test_add_inserts_in_alphabetical_position(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    write_initial(skills_dir, ["chat", "system"])
    add_skill(skills_dir, "pin")
    text = (skills_dir / "__init__.py").read_text(encoding="utf-8")
    assert "from .chat import Chat" in text
    assert "from .pin import Pin" in text
    assert "from .system import System" in text
    assert '__all__ = ["Chat", "Pin", "System"]' in text


def test_add_is_idempotent(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    write_initial(skills_dir, ["chat"])
    add_skill(skills_dir, "chat")
    text = (skills_dir / "__init__.py").read_text(encoding="utf-8")
    assert text.count("from .chat import Chat") == 1


def test_remove_drops_a_skill(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    write_initial(skills_dir, ["chat", "pin", "system"])
    remove_skill(skills_dir, "pin")
    text = (skills_dir / "__init__.py").read_text(encoding="utf-8")
    assert "from .pin import Pin" not in text
    assert "Pin" not in text.split("__all__")[1]
