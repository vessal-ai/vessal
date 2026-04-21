"""test_hull_public_api — Unit tests for Hull public interface.

Verifies that Hull interacts with the outside world through a limited set of public methods
and does not expose internal state such as ns or event_queue.
"""
import queue as queue_mod
import time
from unittest.mock import MagicMock, patch

import pytest

from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream
from vessal.ark.shell.hull.cell.protocol import FRAME_SCHEMA_VERSION


def _frame_dict(number: int, **kwargs) -> dict:
    return {
        "schema_version": FRAME_SCHEMA_VERSION,
        "number": number,
        "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
        "pong": {"think": "", "action": {"operation": kwargs.get("operation", ""), "expect": ""}},
        "observation": {
            "stdout": kwargs.get("stdout", ""),
            "diff": kwargs.get("diff", ""),
            "error": kwargs.get("error", None),
            "verdict": None,
        },
    }


def _make_hull_with_mock_cell(tmp_path):
    """Create a minimal Hull instance with Cell and LLM calls mocked.

    Generates a minimal hull.toml and SOUL.md under tmp_path,
    creates a Hull instance without starting the event loop.
    """
    # Minimal hull.toml
    (tmp_path / "hull.toml").write_text(
        '[agent]\nname = "test"\n[cell]\n[hull]\nskills = []\n',
        encoding="utf-8",
    )
    (tmp_path / "SOUL.md").write_text("# test", encoding="utf-8")
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=fake\nOPENAI_BASE_URL=http://fake\nOPENAI_MODEL=fake\n",
        encoding="utf-8",
    )

    from vessal.ark.shell.hull.hull import Hull
    hull = Hull(str(tmp_path))
    return hull


class TestHullWake:
    """Hull.wake() — the sole wake entry point."""

    def test_wake_puts_event_into_internal_queue(self, tmp_path):
        """wake(reason) delivers an event to the internal event queue."""
        hull = _make_hull_with_mock_cell(tmp_path)
        hull.wake("user_message")
        # Internal queue should have one event
        event = hull._event_loop.event_queue.get(timeout=1)
        assert event["reason"] == "user_message"

    def test_wake_default_reason(self, tmp_path):
        """wake() defaults reason to 'external' when called without arguments."""
        hull = _make_hull_with_mock_cell(tmp_path)
        hull.wake()
        event = hull._event_loop.event_queue.get(timeout=1)
        assert event["reason"] == "external"

    def test_wake_passes_metadata(self, tmp_path):
        """wake() can pass additional metadata."""
        hull = _make_hull_with_mock_cell(tmp_path)
        hull.wake("webhook", source="github")
        event = hull._event_loop.event_queue.get(timeout=1)
        assert event["reason"] == "webhook"
        assert event["source"] == "github"


class TestHullStatus:
    """Hull.status() — Agent status query."""

    def test_status_returns_dict(self, tmp_path):
        """status() returns a dict containing idle, frame, and wake."""
        hull = _make_hull_with_mock_cell(tmp_path)
        result = hull.status()
        assert isinstance(result, dict)
        assert "idle" in result
        assert "frame" in result
        assert "wake" in result

    def test_status_reflects_namespace_values(self, tmp_path):
        """status() values reflect the current state in namespace."""
        hull = _make_hull_with_mock_cell(tmp_path)
        # Manually set namespace values to verify
        hull._cell.ns["_sleeping"] = True
        hull._cell.ns["_frame"] = 42
        hull._cell.ns["_wake"] = "heartbeat"
        result = hull.status()
        assert result["idle"] is True
        assert result["frame"] == 42
        assert result["wake"] == "heartbeat"

    def test_status_does_not_expose_namespace_reference(self, tmp_path):
        """status() returns a snapshot dict; modifying it does not affect namespace."""
        hull = _make_hull_with_mock_cell(tmp_path)
        result = hull.status()
        result["idle"] = "tampered"
        assert hull._cell.ns.get("_sleeping") != "tampered"


class TestHullNextAlarm:
    """Hull.next_alarm() — Agent's scheduled next wake time."""

    def test_next_alarm_default_none(self, tmp_path):
        """Returns None when no alarm is set."""
        hull = _make_hull_with_mock_cell(tmp_path)
        assert hull.next_alarm() is None

    def test_next_alarm_reads_from_namespace(self, tmp_path):
        """After Agent sets _next_wake, next_alarm() returns that timestamp."""
        hull = _make_hull_with_mock_cell(tmp_path)
        future = time.time() + 3600
        hull._cell.ns["_next_wake"] = future
        result = hull.next_alarm()
        assert result == pytest.approx(future, abs=1.0)


class TestHullRunMethods:
    """Hull.run() and Hull.step() — lifecycle methods."""

    def test_hull_has_run_method(self, tmp_path):
        """Hull has a run() method (replaces the old run_forever)."""
        hull = _make_hull_with_mock_cell(tmp_path)
        assert hasattr(hull, "run")
        assert callable(hull.run)

    def test_hull_has_step_method(self, tmp_path):
        """Hull has a step() method (single wake cycle)."""
        hull = _make_hull_with_mock_cell(tmp_path)
        assert hasattr(hull, "step")
        assert callable(hull.step)

    def test_hull_no_run_forever(self, tmp_path):
        """Hull no longer has a run_forever() method."""
        hull = _make_hull_with_mock_cell(tmp_path)
        assert not hasattr(hull, "run_forever")


class TestHullFrames:
    """Hull.frames() — frame log query."""

    def test_frames_returns_list(self, tmp_path):
        """frames() returns a list."""
        hull = _make_hull_with_mock_cell(tmp_path)
        result = hull.frames()
        assert isinstance(result, list)

    def test_frames_after_filters(self, tmp_path):
        """frames(after=N) returns only frames with number > N."""
        hull = _make_hull_with_mock_cell(tmp_path)
        fs = FrameStream()
        fs.commit_frame(_frame_dict(1, diff="+a = 1"))
        fs.commit_frame(_frame_dict(2, diff="+b = 2"))
        fs.commit_frame(_frame_dict(3, diff="+c = 3"))
        hull._cell.ns["_frame_stream"] = fs
        result = hull.frames(after=1)
        assert len(result) == 2
        assert result[0]["number"] == 2

    def test_frames_returns_copy(self, tmp_path):
        """frames() returns a copy; modifications do not affect internal state."""
        hull = _make_hull_with_mock_cell(tmp_path)
        fs = FrameStream()
        fs.commit_frame(_frame_dict(1))
        hull._cell.ns["_frame_stream"] = fs
        result = hull.frames()
        result.append({"number": 999})
        assert hull._cell.ns["_frame_stream"].hot_frame_count() == 1
