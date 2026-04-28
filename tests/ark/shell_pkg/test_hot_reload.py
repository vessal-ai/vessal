"""Tests for watchfiles-driven hot reload dispatch."""
from pathlib import Path

from vessal.ark.shell.cli.hot_reload import classify_change


def test_soul_md_classified_as_soul(tmp_path):
    p = tmp_path / "SOUL.md"
    assert classify_change(str(p), project_dir=tmp_path) == ("soul", None)


def test_skill_py_classified_as_skill(tmp_path):
    (tmp_path / "skills" / "chat").mkdir(parents=True)
    p = tmp_path / "skills" / "chat" / "skill.py"
    assert classify_change(str(p), project_dir=tmp_path) == ("skill", "chat")


def test_hull_toml_classified_as_hull(tmp_path):
    p = tmp_path / "hull.toml"
    assert classify_change(str(p), project_dir=tmp_path) == ("hull_toml", None)


def test_unrelated_file_returns_none(tmp_path):
    p = tmp_path / "README.md"
    assert classify_change(str(p), project_dir=tmp_path) is None
