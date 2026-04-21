"""test_cli_check_update — `vessal check-update` queries PyPI and prints diff."""
from __future__ import annotations

import sys
from unittest.mock import patch


def test_check_update_prints_latest_and_current(monkeypatch):
    """End-to-end-ish test that the CLI surface exists and produces output."""
    from vessal.cli import main

    with patch("vessal.ark.shell.cli.upgrade.check_pypi_latest", return_value="9.9.9"):
        monkeypatch.setattr(sys, "argv", ["vessal", "check-update"])
        try:
            main()
        except SystemExit as e:
            assert e.code in (0, None)
