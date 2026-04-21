"""test_create_wizard_no_subprocess — wizard must not shell out to `vessal init`."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def test_create_wizard_does_not_call_subprocess(tmp_path):
    """After refactor, `_scaffold` must call write_project_scaffold directly."""
    from vessal.ark.shell.tui.create_wizard import _scaffold

    target = tmp_path / "alpha"
    answers = {"name": "alpha", "api_key": "", "base_url": "", "model": "", "dockerize": False}

    with patch("subprocess.check_call") as mock_subproc:
        _scaffold(target, answers)

    mock_subproc.assert_not_called()
    assert (target / "hull.toml").exists()
    assert (target / ".env").exists()
