"""Writer error paths: operation/expect raised → errors row + obs/verdict_error_id linkage."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from vessal.ark.shell.hull.cell.kernel.frame_log import FrameLog, open_db
from vessal.ark.shell.hull.cell.kernel.frame_log.types import (
    ErrorOnSource,
    FrameWriteSpec,
)


def _base_spec(n: int) -> FrameWriteSpec:
    return FrameWriteSpec(
        n=n,
        pong_think="t",
        pong_operation="raise RuntimeError('boom')",
        pong_expect="",
        obs_stdout="",
        obs_stderr="",
        obs_diff_json="{}",
        operation_error=None,
        verdict_value="null",
        verdict_error=None,
        signals=[],
    )


def test_operation_error_writes_errors_row(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(db)
    spec = _base_spec(1)
    spec = replace(spec, operation_error=ErrorOnSource("operation", None, "Traceback ... RuntimeError: boom\n"))
    log.write_frame(spec)
    err = db.execute(
        "SELECT layer, n_start, source, source_detail, format_text FROM errors"
    ).fetchall()
    assert err == [(0, 1, "operation", None, "Traceback ... RuntimeError: boom\n")]


def test_obs_error_id_links_to_errors_row(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(db)
    spec = _base_spec(1)
    spec = replace(spec, operation_error=ErrorOnSource("operation", None, "tb"))
    log.write_frame(spec)
    fc_err_id = db.execute("SELECT obs_error_id FROM frame_content WHERE n=1").fetchone()[0]
    err_id = db.execute("SELECT id FROM errors").fetchone()[0]
    assert fc_err_id == err_id


def test_verdict_error_writes_separate_errors_row(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(db)
    spec = _base_spec(1)
    spec = replace(spec, verdict_error=ErrorOnSource("expect", None, "expect tb"))
    log.write_frame(spec)
    sources = [r[0] for r in db.execute("SELECT source FROM errors ORDER BY id").fetchall()]
    assert sources == ["expect"]
    fc = db.execute("SELECT obs_error_id, verdict_error_id FROM frame_content").fetchone()
    assert fc[0] is None and fc[1] is not None


def test_both_errors_in_one_frame(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(db)
    spec = _base_spec(1)
    spec = replace(
        spec,
        operation_error=ErrorOnSource("operation", None, "op tb"),
        verdict_error=ErrorOnSource("expect", None, "exp tb")
    )
    log.write_frame(spec)
    rows = db.execute("SELECT source, format_text FROM errors ORDER BY id").fetchall()
    assert rows == [("operation", "op tb"), ("expect", "exp tb")]
    fc = db.execute("SELECT obs_error_id, verdict_error_id FROM frame_content").fetchone()
    assert fc[0] is not None and fc[1] is not None and fc[0] != fc[1]
