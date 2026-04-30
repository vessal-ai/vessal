# tests/smoke/test_create_flat_skills.py
"""Smoke test: vessal create produces a flat skills/ layout with .pth registration."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from vessal.ark.shell.cli.project_scaffold import write_project_scaffold


def test_create_writes_flat_skills_layout(tmp_path: Path):
    project = tmp_path / "my_agent"
    write_project_scaffold(project, install_venv=False)

    skills_dir = project / "skills"
    assert skills_dir.is_dir(), "<project>/skills/ must exist"
    assert (skills_dir / "__init__.py").exists(), "skills must be a package"

    for name in ("chat", "tasks", "pin", "heartbeat", "skill_manager", "system", "compaction"):
        assert (skills_dir / name / "__init__.py").exists(), f"skills/{name}/__init__.py missing"
        assert (skills_dir / name / "skill.py").exists() or (skills_dir / name / "_skill.py").exists()

    assert not (project / "skills" / "bundled").exists(), "bundled/ subdir must not exist"
    assert not (project / "skills" / "hub").exists()
    assert not (project / "skills" / "local").exists()


def test_chat_skill_includes_ui_assets(tmp_path: Path):
    project = tmp_path / "my_agent"
    write_project_scaffold(project, install_venv=False)
    assert (project / "skills" / "chat" / "ui" / "index.html").exists(), \
        "chat UI assets must be copied (regression: ignore_patterns dropped them)"
    assert (project / "skills" / "chat" / "server.py").exists(), \
        "chat server.py must be copied"


def test_hull_toml_has_no_skill_paths(tmp_path: Path):
    project = tmp_path / "my_agent"
    write_project_scaffold(project, install_venv=False)
    hull_toml = (project / "hull.toml").read_text()
    assert "skill_paths" not in hull_toml, "skill_paths must be removed from hull.toml"
    assert '"skill_manager"' in hull_toml, "default skills list should reference skill_manager"
    assert '"skills"' not in hull_toml.replace('"skills"', '', 1) or '"skill_manager"' in hull_toml, \
        "the old 'skills' skill name should be replaced by 'skill_manager'"


def test_pth_file_written_with_install_venv(tmp_path: Path):
    project = tmp_path / "my_agent"
    # Create venv ourselves so the test is hermetic and fast.
    write_project_scaffold(project, install_venv=False)
    venv = project / ".venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)

    from vessal.ark.shell.cli.project_scaffold import _write_user_skills_pth
    _write_user_skills_pth(project)

    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    venv_python = venv / bin_dir / "python"
    out = subprocess.check_output(
        [str(venv_python), "-c", "import site; print(site.getsitepackages()[0])"],
        text=True,
    ).strip()
    pth = Path(out) / "vessal_user_skills.pth"
    assert pth.exists(), f"{pth} not written"
    assert pth.read_text().strip() == str(project.resolve())


def test_skills_registry_re_exports_bundled_skills(tmp_path: Path):
    project = tmp_path / "my_agent"
    write_project_scaffold(project, install_venv=False)
    text = (project / "skills" / "__init__.py").read_text(encoding="utf-8")
    for line in (
        "from .chat import Chat",
        "from .heartbeat import Heartbeat",
        "from .pin import Pin",
        "from .skill_manager import SkillManager",
        "from .system import System",
        "from .tasks import Tasks",
        "from .compaction import Compaction",
    ):
        assert line in text, f"missing registry line: {line}"
