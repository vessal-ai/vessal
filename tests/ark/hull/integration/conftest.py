"""tests/integration/conftest.py — Shared fixtures for integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a minimal Vessal project directory (with hull.toml)."""
    toml = (tmp_path / "hull.toml")
    toml.write_text("[agent]\n[cell]\n[compression]\nenabled = false\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """Create an empty skills directory and return its path."""
    d = tmp_path / "skills"
    d.mkdir()
    return d
