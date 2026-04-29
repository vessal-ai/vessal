"""test_frame_log_reader.py — spec §4.10 SQLite-based frame_stream rendering."""
from __future__ import annotations

import sqlite3

import pytest

from vessal.ark.shell.hull.cell.kernel.frame_log import open_db
from vessal.ark.shell.hull.cell.kernel.frame_log.reader import render_frame_stream
from vessal.ark.shell.hull.cell.kernel.frame_log.types import FrameWriteSpec, SignalRow
from vessal.ark.shell.hull.cell.kernel.frame_log import FrameLog
from vessal.ark.shell.hull.cell.protocol import (
    Entry, FrameContent, FrameStream, SummaryContent,
)


def _spec(n: int, op: str = "x = 1") -> FrameWriteSpec:
    return FrameWriteSpec(
        n=n,
        pong_think="",
        pong_operation=op,
        pong_expect="True",
        obs_stdout="",
        obs_stderr="",
        obs_diff_json="[]",
        operation_error=None,
        verdict_value="true",
        verdict_errors=[],
        signals=[],
    )


def test_empty_db_returns_empty_framestream(tmp_path):
    conn = open_db(str(tmp_path / "fl.sqlite"))
    fs = render_frame_stream(conn)
    assert isinstance(fs, FrameStream)
    assert fs.entries == []


def test_three_layer0_entries_returned_in_n_start_asc(tmp_path):
    conn = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(conn)
    log.write_frame(_spec(1, "a = 1"))
    log.write_frame(_spec(2, "b = 2"))
    log.write_frame(_spec(3, "c = 3"))

    fs = render_frame_stream(conn)
    assert [e.n_start for e in fs.entries] == [1, 2, 3]
    assert all(e.layer == 0 for e in fs.entries)
    assert isinstance(fs.entries[0].content, FrameContent)
    assert fs.entries[0].content.operation == "a = 1"


def test_layer1_covers_layer0_range(tmp_path):
    """Spec §4.9 R2: layer=1 entry covering [1..16] hides all layer=0 entries n in [1..16]."""
    conn = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(conn)
    for n in range(1, 18):
        log.write_frame(_spec(n))

    conn.execute(
        "INSERT INTO entries (layer, n_start, n_end) VALUES (1, 1, 16)"
    )
    conn.execute(
        "INSERT INTO summary_content (layer, n_start, schema_version, body) "
        "VALUES (1, 1, 1, 'summary text')"
    )
    conn.commit()

    fs = render_frame_stream(conn)
    assert fs.entries[0].layer == 1
    assert fs.entries[0].n_start == 1
    assert fs.entries[0].n_end == 16
    assert isinstance(fs.entries[0].content, SummaryContent)
    assert fs.entries[0].content.body == "summary text"
    assert all(e.n_start == 17 for e in fs.entries[1:])


def test_signals_aggregated_per_n_start(tmp_path):
    conn = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(conn)
    log.write_frame(FrameWriteSpec(
        n=1,
        pong_think="",
        pong_operation="",
        pong_expect="True",
        obs_stdout="",
        obs_stderr="",
        obs_diff_json="[]",
        operation_error=None,
        verdict_value="true",
        verdict_errors=[],
        signals=[
            SignalRow("ChatSkill", "chat", "L", '{"unread": 3}', None),
            SignalRow("ClockSkill", "clock", "G", '{"now": "t"}', None),
        ],
    ))

    fs = render_frame_stream(conn)
    assert len(fs.entries) == 1
    fc = fs.entries[0].content
    assert isinstance(fc, FrameContent)
    assert fc.signals == {
        ("ChatSkill", "chat", "L"): {"unread": 3},
        ("ClockSkill", "clock", "G"): {"now": "t"},
    }


def test_two_layer1_entries_sorted_by_n_start_asc(tmp_path):
    """Spec §4.9: within same layer, n_start ASC."""
    conn = open_db(str(tmp_path / "fl.sqlite"))
    log = FrameLog(conn)
    for n in range(1, 33):
        log.write_frame(_spec(n))

    conn.execute("INSERT INTO entries VALUES (1, 1, 16)")
    conn.execute("INSERT INTO entries VALUES (1, 17, 32)")
    conn.execute(
        "INSERT INTO summary_content VALUES (1, 1, 1, 'first')"
    )
    conn.execute(
        "INSERT INTO summary_content VALUES (1, 17, 1, 'second')"
    )
    conn.commit()

    fs = render_frame_stream(conn)
    assert [(e.layer, e.n_start) for e in fs.entries] == [(1, 1), (1, 17)]


class TestReaderShapeAlignedWithSpec:
    """reader returns Verdict.to_dict() shape for verdict and list for diff."""

    def _seed_one_frame(self, db_path, *, verdict_json: str | None, diff_json: str):
        from vessal.ark.shell.hull.cell.kernel.frame_log.schema import open_db
        from vessal.ark.shell.hull.cell.kernel.frame_log.types import FrameWriteSpec
        from vessal.ark.shell.hull.cell.kernel.frame_log.writer import FrameLog
        conn = open_db(str(db_path))
        FrameLog(conn).write_frame(FrameWriteSpec(
            n=1,
            pong_think="", pong_operation="x = 1", pong_expect="",
            obs_stdout="", obs_stderr="", obs_diff_json=diff_json,
            operation_error=None,
            verdict_value=verdict_json,
            verdict_errors=[], signals=[],
        ))
        return conn

    def test_reader_observation_diff_is_list(self, tmp_path):
        from vessal.ark.shell.hull.cell.kernel.frame_log.reader import render_frame_stream
        conn = self._seed_one_frame(
            tmp_path / "fl.sqlite",
            verdict_json=None,
            diff_json='[{"op":"+","name":"x","type":"int"}]',
        )
        fs = render_frame_stream(conn)
        fc = fs.entries[0].content
        assert fc.observation["diff"] == [{"op": "+", "name": "x", "type": "int"}]

    def test_reader_verdict_is_total_passed_failures(self, tmp_path):
        from vessal.ark.shell.hull.cell.kernel.frame_log.reader import render_frame_stream
        conn = self._seed_one_frame(
            tmp_path / "fl.sqlite",
            verdict_json='{"total": 2, "passed": 1, "failures": [{"kind":"assertion_failed","assertion":"assert y","message":"y is False"}]}',
            diff_json="[]",
        )
        fs = render_frame_stream(conn)
        fc = fs.entries[0].content
        assert fc.verdict == {
            "total": 2,
            "passed": 1,
            "failures": [{"kind": "assertion_failed", "assertion": "assert y", "message": "y is False"}],
        }

    def test_reader_verdict_is_none_when_value_is_null(self, tmp_path):
        from vessal.ark.shell.hull.cell.kernel.frame_log.reader import render_frame_stream
        conn = self._seed_one_frame(
            tmp_path / "fl.sqlite",
            verdict_json=None,
            diff_json="[]",
        )
        fs = render_frame_stream(conn)
        assert fs.entries[0].content.verdict is None
