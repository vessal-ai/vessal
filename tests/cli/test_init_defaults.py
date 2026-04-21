"""test_init_defaults — vessal create writes the canonical default skills list."""
from __future__ import annotations

from pathlib import Path

from vessal.ark.shell.cli.project_scaffold import write_project_scaffold


def test_init_default_skills_list(tmp_path):
    project = tmp_path / "demo_proj"
    write_project_scaffold(project, install_venv=False)
    hull_toml = (project / "hull.toml").read_text()
    for name in ("tasks", "pin", "chat", "heartbeat", "skills"):
        assert f'"{name}"' in hull_toml, f"{name!r} missing from default skills list:\n{hull_toml}"
