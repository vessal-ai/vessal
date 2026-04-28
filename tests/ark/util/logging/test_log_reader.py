# test_log_reader.py — Unit tests for reader.py
#
# Strategy: write test JSONL to temporary files and verify the behavior of read_frames.

import json
from pathlib import Path

import pytest

from vessal.ark.shell.hull.cell.protocol import (
    Action,
    FrameRecord,
    FrameStream,
    Observation,
    Ping,
    Pong,
    State,
)
from vessal.ark.util.logging.reader import read_frames


# ─────────────────────────────────────────────
# Helper factories
# ─────────────────────────────────────────────


def _make_frame(
    number: int = 1,
    error: BaseException | None = None,
    diff: str = "",
) -> FrameRecord:
    """Construct a test FrameRecord."""
    return FrameRecord(
        number=number,
        ping=Ping(system_prompt="", state=State(frame_stream=FrameStream(entries=[]), signals={})),
        pong=Pong(think="", action=Action(operation="pass", expect="")),
        observation=Observation(stdout="", stderr="", diff=diff, error=error),
    )


def _write_jsonl(path: Path, frames: list[FrameRecord]) -> None:
    """Write a list of FrameRecord objects to a JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for frame in frames:
            f.write(json.dumps(frame.to_dict(), ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────
# read_frames tests
# ─────────────────────────────────────────────


class TestReadFrames:
    def test_read_empty_file(self, tmp_path):
        """An empty JSONL file returns an empty list."""
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        result = read_frames(str(path))
        assert result == []

    def test_read_single_frame(self, tmp_path):
        """A single-frame JSONL returns a list of length 1."""
        path = tmp_path / "single.jsonl"
        _write_jsonl(path, [_make_frame(number=1)])
        result = read_frames(str(path))
        assert len(result) == 1
        assert isinstance(result[0], FrameRecord)

    def test_read_multiple_frames(self, tmp_path):
        """A multi-frame JSONL returns all FrameRecords in order."""
        path = tmp_path / "multi.jsonl"
        frames = [_make_frame(number=i) for i in range(1, 4)]
        _write_jsonl(path, frames)
        result = read_frames(str(path))
        assert len(result) == 3
        assert [r.number for r in result] == [1, 2, 3]

    def test_read_multiple_frames_numbers(self, tmp_path):
        """Multiple frames are read in order with correct frame numbers."""
        path = tmp_path / "types.jsonl"
        _write_jsonl(path, [
            _make_frame(number=1),
            _make_frame(number=2),
        ])
        result = read_frames(str(path))
        assert result[0].number == 1
        assert result[1].number == 2

    def test_legacy_state_key_raises_value_error(self, tmp_path):
        """A line containing 'state' but no schema_version (legacy format) raises ValueError."""
        path = tmp_path / "legacy.jsonl"
        # Legacy format: has state and action keys, no schema_version
        legacy_line = json.dumps({"frame": 1, "state": "x", "action": "pass"})
        path.write_text(legacy_line + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match=str(path)):
            read_frames(str(path))

    def test_legacy_action_key_raises_value_error(self, tmp_path):
        """A line containing 'action' but no schema_version (legacy format) raises ValueError."""
        path = tmp_path / "legacy2.jsonl"
        legacy_line = json.dumps({"frame": 1, "action": "pass"})
        path.write_text(legacy_line + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match=str(path)):
            read_frames(str(path))

    def test_legacy_error_includes_line_number(self, tmp_path):
        """The legacy format error message includes the line number."""
        path = tmp_path / "legacy_ln.jsonl"
        good_line = json.dumps(_make_frame(number=1).to_dict())
        legacy_line = json.dumps({"frame": 2, "state": "x", "action": "pass"})
        path.write_text(good_line + "\n" + legacy_line + "\n", encoding="utf-8")
        with pytest.raises(ValueError) as exc_info:
            read_frames(str(path))
        # Line number should be in the error message (line 2)
        assert "2" in str(exc_info.value)

    def test_read_frames_returns_frame_records(self, tmp_path):
        """All elements returned by read_frames are FrameRecord instances."""
        path = tmp_path / "check_types.jsonl"
        _write_jsonl(path, [_make_frame(number=1)])
        result = read_frames(str(path))
        assert all(isinstance(f, FrameRecord) for f in result)
