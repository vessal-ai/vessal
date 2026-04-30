"""Root test fixtures shared across all test tiers."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Expose vessal's built-in skills as importable `skills.*` for Hull boot scripts.
# Hull boot scripts use `from skills.<name> import Skill`; in a real project the
# project's skills/ dir is on sys.path via a .pth file written by `vessal create`.
# In the test suite there is no installed project, so we point at the source tree.
_VESSAL_SRC = str(Path(__file__).resolve().parents[1] / "src" / "vessal")
if _VESSAL_SRC not in sys.path:
    sys.path.insert(0, _VESSAL_SRC)


@pytest.fixture(autouse=True)
def _clear_vessal_data_dir() -> None:
    """Hull.__init__ sets VESSAL_DATA_DIR as a process-wide side effect.

    Clear it after every test to prevent cross-test state contamination where
    a newly created Chat/Memory Skill reads history from a prior test's data dir.
    """
    yield
    os.environ.pop("VESSAL_DATA_DIR", None)
