"""test_project_scaffold — write_project_scaffold produces a runnable Vessal project."""
from __future__ import annotations

from pathlib import Path

from vessal.ark.shell.cli.project_scaffold import write_project_scaffold


def test_project_scaffold_emits_core_files(tmp_path):
    project = tmp_path / "demo-agent"
    write_project_scaffold(project, install_venv=False)

    assert (project / "hull.toml").exists()
    assert (project / "SOUL.md").exists()
    assert (project / "pyproject.toml").exists()
    assert (project / ".env.example").exists()
    assert (project / ".gitignore").exists()
    assert (project / "gates" / "action_gate.py").exists()
    assert (project / "gates" / "state_gate.py").exists()
    assert (project / "skills" / "local" / "example" / "__init__.py").exists()


def test_project_scaffold_embeds_project_name_in_hull_toml(tmp_path):
    project = tmp_path / "alpha"
    write_project_scaffold(project, install_venv=False)
    assert 'name = "alpha"' in (project / "hull.toml").read_text(encoding="utf-8")


def test_project_scaffold_raises_if_exists(tmp_path):
    project = tmp_path / "existing"
    project.mkdir()
    import pytest
    with pytest.raises(FileExistsError):
        write_project_scaffold(project, install_venv=False)
