"""Hull exposes GET /skills/list — full loaded-skill inventory (not just UI-exposing ones)."""
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def hull(tmp_path):
    (tmp_path / "hull.toml").write_text(
        '[hull]\nskills = []\nskill_paths = []\n'
    )
    (tmp_path / ".env").write_text("OPENAI_API_KEY=test-key\n")
    os.chdir(tmp_path)
    from vessal.ark.shell.hull.hull import Hull
    return Hull(str(tmp_path))


def test_skills_list_returns_all_loaded_skills(hull):
    sm = MagicMock()
    sm.loaded_names = ["chat", "heartbeat"]
    sm.skill_dir = MagicMock(side_effect=lambda n: f"/tmp/skills/{n}")
    sm.skill_summary = MagicMock(side_effect=lambda n: f"{n} summary")
    hull._skill_manager = sm

    status, body = hull.handle("GET", "/skills/list")
    assert status == 200
    names = {s["name"] for s in body["skills"]}
    assert names == {"chat", "heartbeat"}
    for s in body["skills"]:
        assert "summary" in s
        assert "has_ui" in s


def test_logs_route_retired(hull):
    status, body = hull.handle("GET", "/logs")
    assert status == 404
    status, body = hull.handle("GET", "/logs/raw")
    assert status == 404
