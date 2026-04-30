"""console.py — Real-time terminal frame output formatting; writes per-frame summaries and run summaries to sys.stderr."""

from __future__ import annotations

import sys
from pathlib import Path

# ANSI color codes
_COLOR_RESET = "\033[0m"
_COLOR_RED = "\033[31m"  # error frames


def _supports_ansi() -> bool:
    """Detect whether the terminal supports ANSI colors."""
    return sys.stderr.isatty()


def _colorize(text: str, color: str) -> str:
    """Apply an ANSI color to text (if the terminal supports it)."""
    if not _supports_ansi():
        return text
    return f"{color}{text}{_COLOR_RESET}"


def print_frame_line(frame: "dict") -> None:
    """Print a one-line summary of a frame to the terminal.

    Format:
        frame {number:>3d} | {operation_summary:<50}

    Where:
    - operation_summary: first line of the operation code, truncated to 50 characters with "..."

    Error frames are shown in red, with operation_summary replaced by "[ERROR] {first line of error}".

    Output goes to sys.stderr (does not pollute stdout, compatible with pipes).

    Args:
        frame: Frame dict.
    """
    number = frame.get("number", 0)
    obs = frame.get("observation") or {}
    error = obs.get("error") if isinstance(obs, dict) else None
    pong = frame.get("pong") or {}
    action = pong.get("action", {}) if isinstance(pong, dict) else {}
    operation = action.get("operation", "") if isinstance(action, dict) else ""

    # Build operation summary
    if error:
        # Error frame: show first line of the error
        error_first_line = error.split("\n")[0] if error else ""
        op_summary = f"[ERROR] {error_first_line}"
    else:
        # Normal frame: show first line of operation
        op_summary = operation.split("\n")[0] if operation else ""

    # Truncate to 50 characters
    if len(op_summary) > 50:
        op_summary = op_summary[:47] + "..."

    # Build output line
    line = f"frame {number:>3d} | {op_summary:<50}"

    # Apply color
    if error:
        line = _colorize(line, _COLOR_RED)

    # Write to stderr
    print(line, file=sys.stderr)


def print_run_summary(run_dir: Path, frames_count: int, finished: bool, port: int = 8420) -> None:
    """Print a one-line summary after a run completes.

    Format (normal completion):
        ✓ {frames_count} frames completed, log: {run_dir}/raw.jsonl

    Format (truncated):
        ✗ truncated after {frames_count} frames (frame limit reached), log: {run_dir}/raw.jsonl

    Output goes to sys.stderr.

    Args:
        run_dir:      Per-run directory path.
        frames_count: Number of frames in this run.
        finished:     Whether the Agent completed normally.
        port:         Shell server port, used to display the viewer URL (default 8420).
    """
    if finished:
        status = "✓"
        message = f"{frames_count} frames completed"
    else:
        status = "✗"
        message = f"truncated after {frames_count} frames (frame limit reached)"

    jsonl_path = run_dir / "raw.jsonl"
    output = f"{status} {message}, log: {jsonl_path}"

    print(output, file=sys.stderr)
