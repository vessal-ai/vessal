"""Test Hull.handle() single-method HTTP interface."""
import os
import pytest
from pathlib import Path


@pytest.fixture
def hull(tmp_path):
    """Create a minimal Hull for handle() testing."""
    (tmp_path / "hull.toml").write_text(
        '[agent]\nname = "test"\nlanguage = "en"\n'
        '[cell]\nmax_frames = 5\n'
        '[hull]\nskills = []\nskill_paths = []\n'
    )
    (tmp_path / ".env").write_text("OPENAI_API_KEY=test-key\n")
    os.chdir(tmp_path)
    from vessal.ark.shell.hull.hull import Hull
    return Hull(str(tmp_path))


class TestHandle:
    """Hull.handle(method, path, body) returns (status, dict)."""

    def test_get_status(self, hull):
        status, data = hull.handle("GET", "/status", None)
        assert status == 200
        assert "sleeping" in data

    def test_get_frames_empty(self, hull):
        status, data = hull.handle("GET", "/frames", None)
        assert status == 200
        assert "frames" in data

    def test_get_frames_with_after(self, hull):
        status, data = hull.handle("GET", "/frames", {"after": 0})
        assert status == 200

    def test_post_wake(self, hull):
        status, data = hull.handle("POST", "/wake", {"reason": "test"})
        assert status == 200
        assert data.get("status") == "accepted"

    def test_post_stop(self, hull):
        status, data = hull.handle("POST", "/stop", None)
        assert status == 200
        assert data.get("status") == "stopping"

    def test_unknown_route_404(self, hull):
        status, data = hull.handle("GET", "/nonexistent", None)
        assert status == 404
        assert "error" in data

    def test_method_mismatch_404(self, hull):
        status, data = hull.handle("POST", "/status", None)
        assert status == 404

