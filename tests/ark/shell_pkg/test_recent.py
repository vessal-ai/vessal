"""Tests for ~/.vessal/recent.json read/write/dedup."""
from vessal.ark.shell.tui.recent import RecentProjects


def test_append_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = RecentProjects()
    r.add("/projects/a")
    r.add("/projects/b")
    assert r.list() == ["/projects/b", "/projects/a"]


def test_dedup_moves_to_front(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = RecentProjects()
    r.add("/projects/a")
    r.add("/projects/b")
    r.add("/projects/a")
    assert r.list() == ["/projects/a", "/projects/b"]


def test_cap_at_20(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = RecentProjects()
    for i in range(25):
        r.add(f"/p/{i}")
    items = r.list()
    assert len(items) == 20
    assert items[0] == "/p/24"


def test_survives_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = RecentProjects()
    assert r.list() == []
