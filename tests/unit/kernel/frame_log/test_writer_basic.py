"""Writer happy path: no errors, no signals → exactly one frame_content + one entries row."""
from __future__ import annotations

from pathlib import Path

from vessal.ark.shell.hull.cell.kernel.frame_log import FrameLog, open_db
from vessal.ark.shell.hull.cell.kernel.frame_log.types import FrameWriteSpec


def _spec(n: int) -> FrameWriteSpec:
    return FrameWriteSpec(
        n=n,
        pong_think="thought",
        pong_operation="x = 1",
        pong_expect="",
        obs_stdout="",
        obs_stderr="",
        obs_diff_json='{"x": ["__missing__", 1]}',
        operation_error=None,
        verdict_value="null",
        signals=[],
    )


def test_write_frame_inserts_one_entries_row(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(db)
    log.write_frame(_spec(1))
    rows = db.execute("SELECT layer, n_start, n_end FROM entries").fetchall()
    assert rows == [(0, 1, 1)]


def test_write_frame_inserts_one_frame_content_row(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(db)
    log.write_frame(_spec(7))
    row = db.execute(
        "SELECT n, pong_think, pong_operation, pong_expect, obs_stdout, obs_diff_json, "
        "obs_error_id, verdict_value FROM frame_content"
    ).fetchone()
    assert row == (7, "thought", "x = 1", "", "", '{"x": ["__missing__", 1]}', None, "null")


def test_write_frame_inserts_no_signals_no_errors(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(db)
    log.write_frame(_spec(1))
    sig_count = db.execute("SELECT count(*) FROM signals").fetchone()[0]
    err_count = db.execute("SELECT count(*) FROM errors").fetchone()[0]
    assert sig_count == 0
    assert err_count == 0


def test_write_frame_two_frames_distinct_rows(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(db)
    log.write_frame(_spec(1))
    log.write_frame(_spec(2))
    ns = db.execute("SELECT n_start FROM entries ORDER BY n_start").fetchall()
    assert ns == [(1,), (2,)]
