"""test_init_defaults — vessal init writes the canonical default skills list."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_init_default_skills_list(tmp_path):
    project = tmp_path / "demo_proj"
    result = subprocess.run(
        [sys.executable, "-m", "vessal.ark.shell.cli", "init", str(project), "--no-venv"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    hull_toml = (project / "hull.toml").read_text()
    for name in ("tasks", "pin", "chat", "heartbeat", "skills"):
        assert f'"{name}"' in hull_toml, f"{name!r} missing from default skills list:\n{hull_toml}"
