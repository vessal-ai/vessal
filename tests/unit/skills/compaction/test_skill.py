"""Unit tests for CompactionSkill — userspace SQLite writer for layer-≥1 entries."""

import pytest


def test_init_stores_main_db_path(tmp_path):
    from vessal.skills.compaction import CompactionSkill

    db = tmp_path / "main_frame_log.sqlite"
    db.touch()
    skill = CompactionSkill(main_db_path=str(db))

    assert skill._main_db_path == str(db)
    assert skill.signal == {}


def test_init_prints_self_introduction(tmp_path, capsys):
    from vessal.skills.compaction import CompactionSkill

    db = tmp_path / "main.sqlite"
    db.touch()
    CompactionSkill(main_db_path=str(db))

    captured = capsys.readouterr()
    assert "CompactionSkill" in captured.out
    assert str(db) in captured.out
