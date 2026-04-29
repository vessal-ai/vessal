"""schema.py — DDL constants and open_db() helper for the 5-table frame_log.

Tables: entries (master) / frame_content (layer=0) / summary_content (layer>=1) / signals / errors.
See docs/architecture/kernel/04-frame-log.md §4.3 for the canonical schema.
"""
from __future__ import annotations

import sqlite3

DDL = """
CREATE TABLE IF NOT EXISTS entries (
    layer    INTEGER NOT NULL,
    n_start  INTEGER NOT NULL,
    n_end    INTEGER NOT NULL,
    PRIMARY KEY (layer, n_start)
);

CREATE TABLE IF NOT EXISTS frame_content (
    n                INTEGER PRIMARY KEY,
    pong_think       TEXT,
    pong_operation   TEXT,
    pong_expect      TEXT,
    obs_stdout       TEXT,
    obs_stderr       TEXT,
    obs_diff_json    TEXT,
    obs_error_id     INTEGER REFERENCES errors(id),
    verdict_value    TEXT
);

CREATE TABLE IF NOT EXISTS summary_content (
    layer          INTEGER NOT NULL,
    n_start        INTEGER NOT NULL,
    schema_version INTEGER NOT NULL,
    body           TEXT    NOT NULL,
    PRIMARY KEY (layer, n_start)
);

CREATE TABLE IF NOT EXISTS signals (
    n_start      INTEGER NOT NULL,
    class_name   TEXT    NOT NULL,
    var_name     TEXT    NOT NULL,
    scope        TEXT    NOT NULL,
    payload_json TEXT,
    error_id     INTEGER REFERENCES errors(id),
    PRIMARY KEY (n_start, class_name, var_name, scope),
    CHECK ((payload_json IS NOT NULL) <> (error_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS errors (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    layer         INTEGER NOT NULL,
    n_start       INTEGER NOT NULL,
    source        TEXT    NOT NULL,
    source_detail TEXT,
    format_text   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entries_n_end ON entries (layer, n_end);
CREATE INDEX IF NOT EXISTS idx_signals_skill ON signals (class_name, var_name);
CREATE INDEX IF NOT EXISTS idx_errors_entry  ON errors  (layer, n_start);
"""


def open_db(path: str) -> sqlite3.Connection:
    """Open (or create) a frame_log SQLite database with WAL + foreign_keys + 5-table schema.

    On open, applies any pending in-place schema migration (currently: drop the
    legacy `verdict_error_id` column from `frame_content`).

    Args:
        path: Filesystem path to the .sqlite file. Created if absent.

    Returns:
        sqlite3.Connection ready for writes. Caller owns lifecycle (must close).
    """
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(DDL)
    _migrate_drop_verdict_error_id(conn)
    return conn


def _migrate_drop_verdict_error_id(conn: sqlite3.Connection) -> None:
    """Drop the legacy `frame_content.verdict_error_id` column if present.

    The column was retired when verdict became a single Verdict.to_dict() JSON
    in `verdict_value` (spec §3.5 / §4.3). Existing databases keep the column
    until this migration drops it. SQLite 3.35+ supports ALTER TABLE DROP COLUMN.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(frame_content)").fetchall()}
    if "verdict_error_id" in cols:
        conn.execute("ALTER TABLE frame_content DROP COLUMN verdict_error_id")
