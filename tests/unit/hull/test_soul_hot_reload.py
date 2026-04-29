"""test_soul_hot_reload.py — SOUL.md hot-reload unit tests."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def soul_env(tmp_path):
    """Create a temp dir with SOUL.md and a mock cell, return (soul_path, cell)."""
    soul_path = tmp_path / "SOUL.md"
    soul_path.write_text("original soul", encoding="utf-8")
    cell = MagicMock()
    cell.L = {}
    return soul_path, cell


def _make_hull_stub(soul_path: Path, cell: MagicMock):
    """Create a minimal Hull-like object with soul hot-reload attributes."""
    from vessal.ark.shell.hull.hull import Hull

    hull = object.__new__(Hull)
    hull._cell = cell
    hull._cell.G = {}
    hull._soul_path = soul_path
    if soul_path.exists():
        hull._soul_text = soul_path.read_text(encoding="utf-8")
        hull._soul_mtime = soul_path.stat().st_mtime
    else:
        hull._soul_text = ""
        hull._soul_mtime = 0.0
    return hull


class TestSoulInitialLoad:
    def test_soul_text_matches_file(self, soul_env):
        """After init, _soul_text equals SOUL.md content."""
        soul_path, cell = soul_env
        hull = _make_hull_stub(soul_path, cell)
        assert hull._soul_text == "original soul"

    def test_soul_mtime_is_set(self, soul_env):
        """After init, _soul_mtime is a positive float."""
        soul_path, cell = soul_env
        hull = _make_hull_stub(soul_path, cell)
        assert hull._soul_mtime > 0

    def test_soul_missing_gives_empty(self, soul_env):
        """When SOUL.md doesn't exist, _soul_text is empty and _soul_mtime is 0."""
        soul_path, cell = soul_env
        soul_path.unlink()
        hull = _make_hull_stub(soul_path, cell)
        assert hull._soul_text == ""
        assert hull._soul_mtime == 0.0


class TestSoulHotReload:
    def test_rewrite_sets_soul_in_ns(self, soul_env):
        """_rewrite_runtime_owned sets ns['_soul'] to current soul text."""
        soul_path, cell = soul_env
        hull = _make_hull_stub(soul_path, cell)
        hull._rewrite_runtime_owned()
        assert cell.G["_soul"] == "original soul"

    def test_modified_soul_detected_next_frame(self, soul_env):
        """After SOUL.md is modified, next _rewrite_runtime_owned picks up the change."""
        soul_path, cell = soul_env
        hull = _make_hull_stub(soul_path, cell)

        hull._rewrite_runtime_owned()
        assert cell.G["_soul"] == "original soul"

        # Simulate Agent modifying SOUL.md at runtime
        # Force mtime change by temporarily backdating the cached mtime
        hull._soul_mtime = 0.0
        soul_path.write_text("evolved soul", encoding="utf-8")

        hull._rewrite_runtime_owned()
        assert cell.G["_soul"] == "evolved soul"
        # mtime cache should be updated to the file's actual mtime (to avoid re-reading next frame)
        assert hull._soul_mtime == soul_path.stat().st_mtime

    def test_unchanged_soul_not_reread(self, soul_env):
        """When SOUL.md hasn't changed, file is not re-read (mtime unchanged)."""
        soul_path, cell = soul_env
        hull = _make_hull_stub(soul_path, cell)

        hull._rewrite_runtime_owned()
        original_mtime = hull._soul_mtime

        hull._rewrite_runtime_owned()
        assert hull._soul_mtime == original_mtime
        assert cell.G["_soul"] == "original soul"

    def test_soul_deleted_at_runtime_keeps_last_value(self, soul_env):
        """If SOUL.md is deleted after initial load, ns['_soul'] keeps last known value."""
        soul_path, cell = soul_env
        hull = _make_hull_stub(soul_path, cell)

        hull._rewrite_runtime_owned()
        assert cell.G["_soul"] == "original soul"

        soul_path.unlink()

        hull._rewrite_runtime_owned()
        # File gone → exists() returns False → skip mtime check → keep cached text
        assert cell.G["_soul"] == "original soul"
