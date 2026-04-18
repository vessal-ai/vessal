"""Tests for picker.build_menu (pure, no I/O)."""
from pathlib import Path

from vessal.ark.shell.tui.picker import build_menu


def test_inside_project_offers_full_menu(tmp_path):
    (tmp_path / "hull.toml").write_text("[agent]\nname='t'\n")
    items = build_menu(tmp_path, recent=[])
    labels = [label for label, _ in items]
    assert "Run dev" in labels
    assert "Open Console" in labels
    assert "Install skill" in labels
    assert "Stop" in labels


def test_outside_project_only_create_and_recent(tmp_path):
    items = build_menu(tmp_path, recent=["/a", "/b"])
    labels = [label for label, _ in items]
    assert labels == ["Create new project", "Open recent…"]


def test_outside_project_no_recent_hides_entry(tmp_path):
    items = build_menu(tmp_path, recent=[])
    labels = [label for label, _ in items]
    assert labels == ["Create new project"]
