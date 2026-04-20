"""conftest — shared fixtures for boot-surface smoke tests."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import pytest


@pytest.fixture
def vessal_cli(tmp_path: Path):
    """Return a callable that runs ``python -m vessal.cli ...`` in ``tmp_path``.

    The callable accepts argv (excluding the program name) and optional stdin,
    and returns the ``subprocess.CompletedProcess``. Timeouts are short so a
    wedged subprocess fails fast instead of hanging CI.
    """

    def _run(
        argv: Iterable[str],
        *,
        stdin: str | None = None,
        cwd: Path | None = None,
        timeout: float = 30.0,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        return subprocess.run(
            [sys.executable, "-m", "vessal.cli", *argv],
            input=stdin,
            cwd=str(cwd or tmp_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

    return _run
