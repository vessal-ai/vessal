"""test_bind_hull_hook — loader calls _bind_hull(hull) after a Skill is injected into ns."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def hull_factory(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hull.toml").write_text(
        "[hull]\nskills = []\nskill_paths = []\n", encoding="utf-8"
    )
    from vessal.ark.shell.hull.hull import Hull

    def build():
        return Hull(str(tmp_path))
    return build


def test_bind_hull_called_when_method_defined(hull_factory, monkeypatch):
    from vessal.skills._base import BaseSkill

    called = {}

    class ProbeSkill(BaseSkill):
        name = "probe"
        description = "test"

        def __init__(self, ns=None):
            super().__init__()

        def _bind_hull(self, hull):
            called["hull"] = hull

    hull = hull_factory()
    # Simulate the loader's post-instantiation path
    monkeypatch.setattr(hull._skill_manager, "load", lambda n: ProbeSkill)
    hull._load_and_instantiate_skill("probe")

    assert called.get("hull") is hull


def test_skill_without_bind_hull_still_loads(hull_factory, monkeypatch):
    from vessal.skills._base import BaseSkill

    class PlainSkill(BaseSkill):
        name = "plain"
        description = "no hook"

    hull = hull_factory()
    monkeypatch.setattr(hull._skill_manager, "load", lambda n: PlainSkill)
    hull._load_and_instantiate_skill("plain")  # must not raise
    assert isinstance(hull._cell.L["plain"], PlainSkill)
