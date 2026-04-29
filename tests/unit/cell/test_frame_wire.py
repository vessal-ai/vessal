"""test_frame_wire.py — Unit tests for flatten_frame_dict.

Verifies that the legacy nested FrameRecord.to_dict() shape becomes the flat
wire shape that mirrors frame_content SQLite columns (kernel doc §4.3).
"""
from __future__ import annotations

from vessal.ark.shell.hull.cell.protocol import (
    Action,
    FrameRecord,
    FrameStream,
    Observation,
    Ping,
    Pong,
    State,
    flatten_frame_dict,
)


def _make_record_dict(
    number: int = 42,
    think: str = "step 1",
    operation: str = "x = 1",
    expect: str = "assert x == 1",
    stdout: str = "out",
    diff: list | None = None,
    error: BaseException | None = None,
) -> dict:
    record = FrameRecord(
        number=number,
        ping=Ping(system_prompt="", state=State(frame_stream=FrameStream(entries=[]), signals={})),
        pong=Pong(think=think, action=Action(operation=operation, expect=expect)),
        observation=Observation(stdout=stdout, stderr="", diff=diff if diff is not None else [], error=error),
    )
    return record.to_dict()


def test_flatten_renames_number_to_n() -> None:
    flat = flatten_frame_dict(_make_record_dict(number=42))
    assert flat["n"] == 42
    assert "number" not in flat


def test_flatten_promotes_pong_fields_to_top_level() -> None:
    flat = flatten_frame_dict(
        _make_record_dict(think="t", operation="op", expect="ex")
    )
    assert flat["pong_think"] == "t"
    assert flat["pong_operation"] == "op"
    assert flat["pong_expect"] == "ex"
    assert "pong" not in flat
    assert "ping" not in flat


def test_flatten_promotes_observation_fields_to_top_level() -> None:
    diff_entry = {"op": "+", "name": "y", "type": "int"}
    flat = flatten_frame_dict(_make_record_dict(stdout="hello", diff=[diff_entry]))
    assert flat["obs_stdout"] == "hello"
    assert flat["obs_diff_json"] == [diff_entry]
    assert flat["obs_stderr"] == ""
    assert flat["obs_error"] is None
    assert "observation" not in flat


def test_flatten_carries_observation_error_text() -> None:
    exc = RuntimeError("FooError")
    flat = flatten_frame_dict(_make_record_dict(error=exc))
    assert flat["obs_error"] is not None
    assert "FooError" in flat["obs_error"]


def test_flatten_verdict_value_when_none() -> None:
    flat = flatten_frame_dict(_make_record_dict())
    assert flat["verdict_value"] is None
    assert flat["verdict_error"] is None


def test_flatten_emits_entry_model_fields() -> None:
    flat = flatten_frame_dict(_make_record_dict(number=7))
    assert flat["layer"] == 0
    assert flat["n_start"] == 7
    assert flat["n_end"] == 7


def test_flatten_emits_empty_signals_list() -> None:
    flat = flatten_frame_dict(_make_record_dict())
    assert flat["signals"] == []


def test_flatten_does_not_mutate_input() -> None:
    d = _make_record_dict()
    snapshot = repr(d)
    flatten_frame_dict(d)
    assert repr(d) == snapshot
