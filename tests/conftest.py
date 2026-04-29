"""Root test fixtures shared across all test tiers."""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _clear_vessal_data_dir() -> None:
    """Hull.__init__ sets VESSAL_DATA_DIR as a process-wide side effect.

    Clear it after every test to prevent cross-test state contamination where
    a newly created Chat/Memory Skill reads history from a prior test's data dir.
    """
    yield
    os.environ.pop("VESSAL_DATA_DIR", None)
