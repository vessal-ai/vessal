"""Tests for Hull.reload_soul and Hull.reload_skill."""
import os
from pathlib import Path

import pytest

from vessal.ark.shell.hull.hull import Hull


def _seed_project(tmp_path: Path) -> Path:
    (tmp_path / "hull.toml").write_text(
        '[agent]\nname = "t"\nlanguage = "en"\n'
        '[core]\ntimeout = 5\n'
        '[cell]\nmax_frames = 3\ncontext_budget = 4096\n'
        '[hull]\nskills = []\nskill_paths = []\n'
    )
    (tmp_path / ".env").write_text("OPENAI_API_KEY=test-key\n")
    (tmp_path / "SOUL.md").write_text("v1")
    return tmp_path


def test_reload_soul_updates_cached_text(tmp_path):
    project = _seed_project(tmp_path)
    os.chdir(project)
    hull = Hull(str(project))
    hull._rewrite_runtime_owned()
    assert hull._soul_text == "v1"
    (project / "SOUL.md").write_text("v2")
    hull.reload_soul()
    assert hull._soul_text == "v2"


def test_reload_skill_rebinds_instance(tmp_path):
    project = _seed_project(tmp_path)
    os.chdir(project)
    hull = Hull(str(project))
    # Without a loaded skill this should be a no-op that returns False.
    assert hull.reload_skill("nonexistent") is False
