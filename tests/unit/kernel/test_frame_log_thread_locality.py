"""test_frame_log_thread_locality — verifies open_read_only opens a fresh
read-only conn that disallows writes and is safe to call cross-thread."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from vessal.ark.shell.hull.cell.kernel.frame_log import open_read_only
from vessal.ark.shell.hull.cell.kernel.frame_log.schema import open_db


def test_open_read_only_can_select(tmp_path: Path):
    db = tmp_path / "frame_log.sqlite"
    open_db(str(db)).close()  # initialize schema then drop

    conn = open_read_only(str(db))
    try:
        rows = conn.execute("SELECT COUNT(*) FROM entries").fetchall()
        assert rows == [(0,)]
    finally:
        conn.close()


def test_open_read_only_rejects_writes(tmp_path: Path):
    db = tmp_path / "frame_log.sqlite"
    open_db(str(db)).close()

    conn = open_read_only(str(db))
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute(
                "INSERT INTO entries(layer, n_start, n_end) VALUES (0, 999, 999)"
            )
    finally:
        conn.close()


def test_open_db_allows_cross_thread_use(tmp_path: Path):
    """Kernel's writer conn opens on init thread, used from worker thread.
    With check_same_thread=False, this no longer raises ProgrammingError."""
    db = tmp_path / "frame_log.sqlite"
    conn = open_db(str(db))
    errors: list[Exception] = []

    def worker():
        try:
            conn.execute("SELECT 1").fetchall()
        except Exception as exc:
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    conn.close()

    assert errors == []


def test_open_read_only_exported_from_package():
    """The helper must be importable as vessal.ark.shell.hull.cell.kernel.frame_log.open_read_only."""
    from vessal.ark.shell.hull.cell.kernel import frame_log
    assert hasattr(frame_log, "open_read_only")
