"""schema migration: open_db drops verdict_error_id from existing frame_content."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from vessal.ark.shell.hull.cell.kernel.frame_log.schema import open_db


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_new_db_does_not_have_verdict_error_id(tmp_path: Path):
    db = tmp_path / "new.sqlite"
    conn = open_db(str(db))
    cols = _columns(conn, "frame_content")
    assert "verdict_error_id" not in cols
    assert "verdict_value" in cols  # spec-mandated still-present column


def test_open_db_migrates_existing_db_drops_verdict_error_id(tmp_path: Path):
    db = tmp_path / "legacy.sqlite"
    legacy = sqlite3.connect(str(db), isolation_level=None)
    legacy.execute(
        "CREATE TABLE frame_content ("
        "n INTEGER PRIMARY KEY, pong_think TEXT, pong_operation TEXT, "
        "pong_expect TEXT, obs_stdout TEXT, obs_stderr TEXT, obs_diff_json TEXT, "
        "obs_error_id INTEGER, verdict_value TEXT, verdict_error_id INTEGER)"
    )
    legacy.execute("INSERT INTO frame_content(n) VALUES (1)")
    legacy.close()

    conn = open_db(str(db))
    cols = _columns(conn, "frame_content")
    assert "verdict_error_id" not in cols
    # Existing data must survive
    rows = conn.execute("SELECT n FROM frame_content").fetchall()
    assert rows == [(1,)]
