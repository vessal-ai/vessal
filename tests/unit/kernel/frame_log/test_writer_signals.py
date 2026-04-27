"""Writer signals path: payload_json rows, error rows, CHECK constraint, multi-skill."""
from __future__ import annotations

import pytest
from pathlib import Path

from vessal.ark.shell.hull.cell.kernel.frame_log import FrameLog, open_db
from vessal.ark.shell.hull.cell.kernel.frame_log.types import (
    ErrorOnSource,
    FrameWriteSpec,
    SignalRow,
)


def _spec_with_signals(n: int, signals: list[SignalRow]) -> FrameWriteSpec:
    return FrameWriteSpec(
        n=n, pong_think="", pong_operation="", pong_expect="",
        obs_stdout="", obs_stderr="", obs_diff_json="{}",
        operation_error=None, verdict_value="null", verdict_error=None,
        signals=signals,
    )


def test_single_payload_signal(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    FrameLog(db).write_frame(_spec_with_signals(1, [
        SignalRow("ChatSkill", "chat_alice", "L", payload_json='{"unread": 3}'),
    ]))
    rows = db.execute(
        "SELECT n_start, class_name, var_name, scope, payload_json, error_id FROM signals"
    ).fetchall()
    assert rows == [(1, "ChatSkill", "chat_alice", "L", '{"unread": 3}', None)]


def test_failed_signal_writes_error_and_links(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    FrameLog(db).write_frame(_spec_with_signals(1, [
        SignalRow("MailSkill", "mail", "L",
                  error=ErrorOnSource("signal_update", "mail", "mail tb")),
    ]))
    sig = db.execute(
        "SELECT class_name, payload_json, error_id FROM signals"
    ).fetchone()
    err = db.execute(
        "SELECT id, source, source_detail, format_text FROM errors"
    ).fetchone()
    assert sig[0] == "MailSkill"
    assert sig[1] is None
    assert sig[2] == err[0]
    assert err[1:] == ("signal_update", "mail", "mail tb")


def test_mixed_signals_one_failed_others_ok(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    FrameLog(db).write_frame(_spec_with_signals(1, [
        SignalRow("ChatSkill",  "chat_alice", "L", payload_json='{"u":3}'),
        SignalRow("ChatSkill",  "chat_bob",   "L", payload_json='{"u":0}'),
        SignalRow("ClockSkill", "clock",      "G", payload_json='{"now":"t"}'),
        SignalRow("MailSkill",  "mail",       "L",
                  error=ErrorOnSource("signal_update", "mail", "boom")),
    ]))
    rows = db.execute(
        "SELECT class_name, payload_json IS NULL AS failed FROM signals "
        "ORDER BY class_name, var_name"
    ).fetchall()
    # Three OK, one failed
    assert sum(1 for r in rows if r[1]) == 1
    assert sum(1 for r in rows if not r[1]) == 3


def test_signal_row_with_both_payload_and_error_raises(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(db)
    bad = SignalRow("X", "x", "L",
                    payload_json='{"a":1}',
                    error=ErrorOnSource("signal_update", "x", "tb"))
    with pytest.raises(ValueError, match="exactly one"):
        log.write_frame(_spec_with_signals(1, [bad]))


def test_signal_row_with_neither_raises(tmp_path: Path) -> None:
    db = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(db)
    bad = SignalRow("X", "x", "L")
    with pytest.raises(ValueError, match="exactly one"):
        log.write_frame(_spec_with_signals(1, [bad]))
