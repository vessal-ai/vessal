"""test_cli_version — `vessal --version` prints installed version."""
from __future__ import annotations

import subprocess
import sys

from importlib import metadata


def test_version_flag_prints_installed_version():
    expected = metadata.version("vessal")
    result = subprocess.run(
        [sys.executable, "-m", "vessal", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    combined = (result.stdout + result.stderr).strip()
    assert expected in combined, f"expected {expected!r} in output, got {combined!r}"
