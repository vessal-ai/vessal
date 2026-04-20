"""test_cli_create — CLI contract: vessal create never emits a Python traceback
for user-recoverable conditions."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from vessal.ark.shell.errors import CliUserError


def test_cli_create_translates_cli_user_error(capsys):
    from vessal.cli import main

    def fake_wizard(_cwd: Path) -> int:
        raise CliUserError("target already exists")

    with patch("sys.argv", ["vessal", "create"]), \
         patch("vessal.ark.shell.tui.create_wizard.run", fake_wizard):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    captured = capsys.readouterr()
    assert "target already exists" in captured.err
    assert "Traceback" not in captured.err
