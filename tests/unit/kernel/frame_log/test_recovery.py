"""Crash recovery: last_committed_frame(), cleanup_partial()."""
from __future__ import annotations

from pathlib import Path

from vessal.ark.shell.hull.cell.kernel.frame_log import FrameLog, open_db
from vessal.ark.shell.hull.cell.kernel.frame_log.types import FrameWriteSpec


def _spec(n: int) -> FrameWriteSpec:
    return FrameWriteSpec(
        n=n, pong_think="", pong_operation="", pong_expect="",
        obs_stdout="", obs_stderr="", obs_diff_json="{}",
        operation_error=None, verdict_value="null", verdict_error=None, signals=[],
    )


def test_last_committed_empty_returns_none(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    assert FrameLog(db).last_committed_frame() is None


def test_last_committed_returns_max_n_start(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(db)
    for n in (1, 2, 3, 5, 7):
        log.write_frame(_spec(n))
    assert log.last_committed_frame() == 7


def test_cleanup_partial_no_orphan_returns_zero(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(db)
    log.write_frame(_spec(1))
    log.write_frame(_spec(2))
    deleted = log.cleanup_partial()
    assert deleted == 0
    assert db.execute("SELECT count(*) FROM frame_content").fetchone()[0] == 2


def test_cleanup_partial_deletes_orphan_frame_content(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(db)
    log.write_frame(_spec(1))
    log.write_frame(_spec(2))
    # Simulate a crashed-mid-frame: frame_content row 3 exists, no entries row.
    db.execute("INSERT INTO frame_content(n, pong_think) VALUES (3, 'partial')")
    db.commit()
    deleted = log.cleanup_partial()
    assert deleted == 1
    assert db.execute("SELECT count(*) FROM frame_content").fetchone()[0] == 2
    assert log.last_committed_frame() == 2


def test_cleanup_partial_on_empty_db(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    db.execute("INSERT INTO frame_content(n, pong_think) VALUES (1, 'orphan')")
    db.commit()
    log = FrameLog(db)
    deleted = log.cleanup_partial()
    assert deleted == 1
    assert log.last_committed_frame() is None
