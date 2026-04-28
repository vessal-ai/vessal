# test_frame_logger.py — Unit tests for FrameLogger
#
# Strategy: write to a temporary directory, do not mock the file system.
# Verifies: open() returns the frames.jsonl path, write_frame writes correct JSON lines,
#           flush behavior, multi-frame ordered append, serialization via to_dict(),
#           and append mode preserving data across runs.

import json
from pathlib import Path

import pytest

from vessal.ark.shell.hull.cell.protocol import (
    FRAME_SCHEMA_VERSION,
    Action,
    FrameRecord,
    FrameStream,
    Observation,
    Ping,
    Pong,
    State,
)
from vessal.ark.util.logging.frame_logger import FrameLogger


# ─────────────────────────────────────────────
# Helper factories
# ─────────────────────────────────────────────


def _make_frame(number: int = 1) -> FrameRecord:
    """Construct a minimal valid FrameRecord for testing."""
    return FrameRecord(
        number=number,
        ping=Ping(system_prompt="", state=State(frame_stream=FrameStream(entries=[]), signals={})),
        pong=Pong(think="", action=Action(operation="pass", expect="")),
        observation=Observation(
            stdout="",
            diff="+my_var = 42",
            error=None,
            verdict=None,
        ),
    )


# ─────────────────────────────────────────────
# Common fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def sample_frame():
    """Return a minimal valid FrameRecord for use in tests."""
    return _make_frame()


# ─────────────────────────────────────────────
# FrameLogger tests
# ─────────────────────────────────────────────


class TestFrameLogger:
    def test_open_returns_file_path(self, tmp_path):
        """open() returns a Path object pointing to the frames.jsonl file (not a directory)."""
        logger = FrameLogger(str(tmp_path))
        result = logger.open()
        logger.close()
        assert isinstance(result, Path)
        assert result.name == "frames.jsonl"
        assert result.is_file()

    def test_open_creates_frames_jsonl(self, tmp_path):
        """open() creates a frames.jsonl file under log_dir."""
        logger = FrameLogger(str(tmp_path))
        logger.open()
        logger.close()
        assert (tmp_path / "frames.jsonl").exists()

    def test_open_creates_dir_if_missing(self, tmp_path):
        """open() automatically creates log_dir if it does not exist."""
        log_dir = tmp_path / "nested" / "logs"
        logger = FrameLogger(str(log_dir))
        logger.open()
        logger.close()
        assert log_dir.exists()
        assert (log_dir / "frames.jsonl").exists()

    def test_write_frame_appends_json_line(self, tmp_path):
        """write_frame() writes one valid JSON line to frames.jsonl."""
        logger = FrameLogger(str(tmp_path))
        logger.open()
        frame = _make_frame()
        logger.write_frame(frame)
        logger.close()

        jsonl_path = tmp_path / "frames.jsonl"
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["number"] == 1

    def test_write_frame_uses_to_dict(self, tmp_path):
        """write_frame() serializes via frame.to_dict() and preserves all fields."""
        logger = FrameLogger(str(tmp_path))
        logger.open()
        frame = _make_frame(number=5)
        logger.write_frame(frame)
        logger.close()

        jsonl_path = tmp_path / "frames.jsonl"
        entry = json.loads(jsonl_path.read_text(encoding="utf-8").strip())
        expected = frame.to_dict()
        assert entry == expected

    def test_write_multiple_frames_in_order(self, tmp_path):
        """Multiple frames are appended to frames.jsonl in order, one per line."""
        logger = FrameLogger(str(tmp_path))
        logger.open()
        for i in range(1, 4):
            logger.write_frame(_make_frame(number=i))
        logger.close()

        jsonl_path = tmp_path / "frames.jsonl"
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3
        for idx, line in enumerate(lines, start=1):
            entry = json.loads(line)
            assert entry["number"] == idx

    def test_write_frame_flushes(self, tmp_path):
        """Reading the file immediately after write_frame() still returns data (flush is effective)."""
        logger = FrameLogger(str(tmp_path))
        logger.open()
        frame = _make_frame()
        logger.write_frame(frame)
        # Without calling close() — flush guarantees data is on disk
        jsonl_path = tmp_path / "frames.jsonl"
        content = jsonl_path.read_text(encoding="utf-8")
        logger.close()
        assert content.strip() != ""

    def test_write_frame_schema_version_present(self, tmp_path):
        """Each log line contains a schema_version field."""
        logger = FrameLogger(str(tmp_path))
        logger.open()
        logger.write_frame(_make_frame())
        logger.close()

        jsonl_path = tmp_path / "frames.jsonl"
        entry = json.loads(jsonl_path.read_text(encoding="utf-8").strip())
        assert entry["schema_version"] == FRAME_SCHEMA_VERSION

    def test_write_frame_accepts_dict(self, tmp_path):
        """write_frame() accepts a frame dict (StepResult.frame format) and serializes it directly."""
        logger = FrameLogger(str(tmp_path))
        logger.open()
        frame_dict = _make_frame().to_dict()
        logger.write_frame(frame_dict)  # type: ignore[arg-type]
        logger.close()

        jsonl_path = tmp_path / "frames.jsonl"
        entry = json.loads(jsonl_path.read_text(encoding="utf-8").strip())
        assert entry["number"] == 1

    def test_write_frame_before_open_raises(self, tmp_path, sample_frame):
        """write_frame() without prior open() raises RuntimeError."""
        logger = FrameLogger(str(tmp_path / "logs"))
        with pytest.raises(RuntimeError, match="open()"):
            logger.write_frame(sample_frame)

    def test_close_idempotent(self, tmp_path):
        """Calling close() multiple times does not raise an error."""
        logger = FrameLogger(str(tmp_path))
        logger.open()
        logger.close()
        logger.close()  # second close should not raise

    def test_raw_jsonl_path_property(self, tmp_path):
        """raw_jsonl_path property returns the full path to frames.jsonl."""
        logger = FrameLogger(str(tmp_path))
        logger.open()
        jsonl_path = logger.raw_jsonl_path
        logger.close()
        assert jsonl_path == tmp_path / "frames.jsonl"

    def test_raw_jsonl_path_none_before_open(self, tmp_path):
        """raw_jsonl_path returns None before open() is called."""
        logger = FrameLogger(str(tmp_path))
        assert logger.raw_jsonl_path is None

    def test_append_mode_preserves_previous_runs(self, tmp_path):
        """A second open() appends rather than truncating, preserving data from previous runs."""
        logger1 = FrameLogger(str(tmp_path))
        logger1.open()
        logger1.write_frame(_make_frame(number=1))
        logger1.close()

        logger2 = FrameLogger(str(tmp_path))
        logger2.open()
        logger2.write_frame(_make_frame(number=2))
        logger2.close()

        jsonl_path = tmp_path / "frames.jsonl"
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["number"] == 1
        assert json.loads(lines[1])["number"] == 2

    def test_close_does_not_generate_md_reports(self, tmp_path):
        """close() no longer generates summary.md or detailed.md (reporter has been removed)."""
        logger = FrameLogger(str(tmp_path))
        logger.open()
        logger.write_frame(_make_frame())
        logger.close()
        assert not (tmp_path / "summary.md").exists()
        assert not (tmp_path / "detailed.md").exists()

    def test_frame_type_not_in_log(self, tmp_path):
        """FrameRecord does not contain frame_type, so the written JSON should not contain that field either."""
        logger = FrameLogger(str(tmp_path))
        logger.open()
        logger.write_frame(_make_frame())
        logger.close()
        jsonl_path = tmp_path / "frames.jsonl"
        entry = json.loads(jsonl_path.read_text(encoding="utf-8").strip())
        assert "frame_type" not in entry
        assert "wake_reason" not in entry
