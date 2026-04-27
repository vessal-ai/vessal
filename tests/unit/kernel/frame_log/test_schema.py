"""Schema tests: open_db creates 5 tables with WAL + foreign_keys enabled."""
from __future__ import annotations
import sqlite3
from pathlib import Path

from vessal.ark.shell.hull.cell.kernel.frame_log.schema import open_db


def test_open_db_creates_five_tables(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "frame_log.sqlite"))
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = {r[0] for r in rows}
    # Filter out sqlite_sequence (created by AUTOINCREMENT)
    names.discard("sqlite_sequence")
    assert names == {"entries", "errors", "frame_content", "signals", "summary_content"}


def test_open_db_enables_wal(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "frame_log.sqlite"))
    mode = db.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_open_db_enables_foreign_keys(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "frame_log.sqlite"))
    fk = db.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


def test_open_db_is_idempotent(tmp_path: Path) -> None:
    path = str(tmp_path / "frame_log.sqlite")
    open_db(path).close()
    db = open_db(path)
    rows = db.execute("SELECT count(*) FROM entries").fetchone()
    assert rows == (0,)


def test_entries_primary_key_layer_n_start(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "frame_log.sqlite"))
    db.execute("INSERT INTO entries(layer, n_start, n_end) VALUES (0, 1, 1)")
    db.commit()
    try:
        db.execute("INSERT INTO entries(layer, n_start, n_end) VALUES (0, 1, 1)")
        db.commit()
    except sqlite3.IntegrityError:
        return
    raise AssertionError("expected IntegrityError on duplicate (layer, n_start)")


def test_signals_check_constraint_payload_xor_error(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "frame_log.sqlite"))
    db.execute("INSERT INTO entries(layer, n_start, n_end) VALUES (0, 1, 1)")
    db.commit()
    # Both NULL → CHECK fails
    try:
        db.execute(
            "INSERT INTO signals(n_start, class_name, var_name, scope, payload_json, error_id) "
            "VALUES (1, 'X', 'x', 'L', NULL, NULL)"
        )
        db.commit()
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("expected IntegrityError when both payload_json and error_id are NULL")
