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


@pytest.fixture
def main_db(tmp_path):
    """Create a fresh frame_log SQLite using the production schema."""
    from vessal.ark.shell.hull.cell.kernel.frame_log.schema import open_db
    path = tmp_path / "main_frame_log.sqlite"
    conn = open_db(str(path))
    conn.close()
    return str(path)


def test_write_summary_inserts_entries_and_summary_atomically(main_db):
    import sqlite3
    from vessal.skills.compaction import CompactionSkill

    skill = CompactionSkill(main_db_path=main_db)
    skill.write_summary(
        layer=1, n_start=1, n_end=4, schema_version=1,
        body="range:\n  n_start: 1\n  n_end: 4\nintent: stub\n",
    )

    conn = sqlite3.connect(main_db)
    try:
        entries = conn.execute(
            "SELECT layer, n_start, n_end FROM entries WHERE layer=1"
        ).fetchall()
        summaries = conn.execute(
            "SELECT layer, n_start, schema_version, body FROM summary_content WHERE layer=1"
        ).fetchall()
    finally:
        conn.close()

    assert entries == [(1, 1, 4)]
    assert len(summaries) == 1
    assert summaries[0][:3] == (1, 1, 1)
    assert "intent: stub" in summaries[0][3]


def test_write_summary_rolls_back_on_pk_conflict(main_db):
    import sqlite3
    from vessal.skills.compaction import CompactionSkill

    skill = CompactionSkill(main_db_path=main_db)
    skill.write_summary(layer=1, n_start=1, n_end=4, schema_version=1, body="first")

    with pytest.raises(sqlite3.IntegrityError):
        skill.write_summary(layer=1, n_start=1, n_end=4, schema_version=1, body="dup")

    conn = sqlite3.connect(main_db)
    try:
        rows = conn.execute("SELECT body FROM summary_content WHERE layer=1").fetchall()
    finally:
        conn.close()
    assert rows == [("first",)]
