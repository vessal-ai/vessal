from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from vessal.cell.kernel.frame_log import open_read_only
from vessal.cell.kernel.frame_log.schema import open_db


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
    db = tmp_path / "frame_log.sqlite"
    conn = open_db(str(db))
    errors: list[Exception] = []

    def worker():
        try:
            conn.execute(
                "INSERT INTO entries(layer, n_start, n_end) VALUES (0, 1, 1)"
            )
        except Exception as exc:
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    conn.close()

    assert errors == []


def test_open_read_only_exported_from_package():
    from vessal.cell.kernel import frame_log
    assert hasattr(frame_log, "open_read_only")


def test_kernel_exposes_db_path(tmp_path: Path):
    from vessal.cell.kernel.kernel import Kernel
    from vessal.cell.kernel.boot import compose_boot_script, BootSkillEntry

    db = tmp_path / "frame_log.sqlite"
    script = compose_boot_script([
        BootSkillEntry("_system", "System"),
    ])
    kernel = Kernel(boot_script=script, db_path=str(db))

    assert kernel.db_path == str(db)


def test_kernel_db_path_is_none_when_no_db(tmp_path: Path):
    from vessal.cell.kernel.kernel import Kernel
    from vessal.cell.kernel.boot import compose_boot_script, BootSkillEntry

    script = compose_boot_script([
        BootSkillEntry("_system", "System"),
    ])
    kernel = Kernel(boot_script=script, db_path=None)

    assert kernel.db_path is None
