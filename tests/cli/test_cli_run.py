"""test_cli_run — vessal run command tests."""
from unittest.mock import patch

import pytest


def test_vessal_run_requires_goal():
    """vessal run exits with error when --goal argument is missing."""
    from vessal.cli import main
    with patch("sys.argv", ["vessal", "run"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code != 0


def test_vessal_run_exists():
    """vessal run subcommand exists."""
    from vessal.cli import main
    # --help should not raise an error
    with patch("sys.argv", ["vessal", "run", "--help"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
