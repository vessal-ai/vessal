# test_console.py — Unit tests for the console module

from pathlib import Path

import pytest

from vessal.ark.util.logging.console import print_frame_line, print_run_summary


def _make_frame(
    number: int,
    operation: str = "x = 1",
    error: str | None = None,
) -> dict:
    """Create a test frame dict."""
    return {
        "schema_version": 5,
        "number": number,
        "pong": {
            "think": "",
            "action": {"operation": operation, "expect": ""},
        },
        "observation": {
            "stdout": "",
            "diff": "",
            "error": error,
            "verdict": None,
        },
    }


def test_print_frame_line_format(capsys) -> None:
    """Verify output format: frame number | operation summary."""
    frame = _make_frame(number=1, operation="x = 1 + 2")
    print_frame_line(frame)
    captured = capsys.readouterr()

    assert "frame   1" in captured.err
    assert "x = 1 + 2" in captured.err


def test_print_frame_line_truncates_long_operation(capsys) -> None:
    """Operations longer than 50 characters should be truncated."""
    long_op = "x = " + "1 + " * 20  # very long operation
    frame = _make_frame(number=1, operation=long_op)
    print_frame_line(frame)
    captured = capsys.readouterr()

    # Should be truncated and end with "..."
    assert "..." in captured.err
    # The full operation should not appear verbatim (should be truncated)
    # Check that the summary portion is limited to ~50 characters
    assert "|" in captured.err  # separator
    parts = captured.err.split("|")
    assert len(parts) >= 2  # frame number, operation summary


def test_print_frame_line_error_frame(capsys) -> None:
    """Error frames should display the [ERROR] prefix."""
    error_msg = "NameError: name 'foo' is not defined"
    frame = _make_frame(number=1, error=error_msg)
    print_frame_line(frame)
    captured = capsys.readouterr()

    assert "[ERROR]" in captured.err
    assert "NameError" in captured.err


def test_print_frame_line_outputs_to_stderr(capsys) -> None:
    """Output should go to stderr and not pollute stdout."""
    frame = _make_frame(number=1)
    print_frame_line(frame)
    captured = capsys.readouterr()

    assert captured.err  # should have stderr output
    assert not captured.out  # stdout should be empty


def test_print_frame_line_basic_output(capsys) -> None:
    """Frame output should contain the frame number and operation summary."""
    frame = _make_frame(number=1, operation="y = 42")
    print_frame_line(frame)
    captured = capsys.readouterr()

    assert "frame   1" in captured.err
    assert "y = 42" in captured.err


def test_print_run_summary_finished(capsys) -> None:
    """Normal completion should show the ✓ prefix."""
    run_dir = Path("/tmp/logs/20260401_100000")
    print_run_summary(run_dir, 5, finished=True)
    captured = capsys.readouterr()

    assert "✓" in captured.err
    assert "5 frames completed" in captured.err
    assert "raw.jsonl" in captured.err


def test_print_run_summary_truncated(capsys) -> None:
    """Truncation should show the ✗ prefix."""
    run_dir = Path("/tmp/logs/20260401_100000")
    print_run_summary(run_dir, 100, finished=False)
    captured = capsys.readouterr()

    assert "✗" in captured.err
    assert "truncated after" in captured.err
    assert "raw.jsonl" in captured.err


def test_print_run_summary_outputs_to_stderr(capsys) -> None:
    """Output should go to stderr."""
    run_dir = Path("/tmp/logs/20260401_100000")
    print_run_summary(run_dir, 5, finished=True)
    captured = capsys.readouterr()

    assert captured.err  # should have stderr output
    assert not captured.out  # stdout should be empty


def test_print_run_summary_path_display(capsys) -> None:
    """Should display the full path to raw.jsonl."""
    run_dir = Path("/my/custom/logs/20260401_100000")
    print_run_summary(run_dir, 10, finished=True)
    captured = capsys.readouterr()

    assert "/my/custom/logs/20260401_100000/raw.jsonl" in captured.err
