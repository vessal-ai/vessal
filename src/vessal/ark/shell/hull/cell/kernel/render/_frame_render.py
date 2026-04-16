"""_frame_render.py — Frame stream rendering (FrameRecord projection + hard frame deletion).

render_frame_stream(ns, budget_tokens) -> tuple[str, int]
    Render the frame stream text for all frames; physically deletes the oldest frames
    when over budget.
    Returns (frame_stream_text, dropped_count).
    frame_stream_text does not include the "══════ frame stream ══════" header
    (that is concatenated by renderer.py).

project_frame_dict(frame_dict, include_think) -> str
    Project a frame dict (element of _frame_log) into a frame stream text block.
    Retained for dict-based projection scenarios.

project_frame(frame, include_think) -> str
    Project a FrameRecord into human-readable text.
    Called directly by frame/__init__.py shim and tests.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from vessal.ark.util.token_util import estimate_tokens

if TYPE_CHECKING:
    from vessal.ark.shell.hull.cell.protocol import FrameRecord


def project_frame_dict(frame: dict, include_think: bool = True) -> str:
    """Project a frame dict into a human-readable text block.

    Args:
        frame:         Frame dict from _frame_log.
        include_think: Whether to include the [think] section.

    Returns:
        Formatted multi-line string ending with a newline.
    """
    pong = frame["pong"]
    obs = frame["observation"]
    lines: list[str] = []

    lines.append(f"── frame {frame['number']} ──")

    if include_think and pong.get("think"):
        lines.append("[think]")
        lines.append(pong["think"])

    action = pong.get("action", {})
    operation = action.get("operation", "")
    expect = action.get("expect", "")

    lines.append("[operation]")
    lines.append(operation)

    if expect:
        lines.append("[expect]")
        lines.append(expect)

    if obs.get("stdout"):
        lines.append("[stdout]")
        lines.append(obs["stdout"])

    if obs.get("diff"):
        lines.append("[diff]")
        lines.append(obs["diff"])

    if obs.get("error") is not None:
        lines.append("[error]")
        lines.append(obs["error"])

    verdict_data = obs.get("verdict")
    if verdict_data is not None:
        lines.append("[verdict]")
        summary = f"{verdict_data['passed']}/{verdict_data['total']} assertions passed"
        if verdict_data.get("failures"):
            lines.append(summary)
            for f in verdict_data["failures"]:
                lines.append(f"  [{f['kind']}] {f['assertion']}: {f['message']}")
        else:
            lines.append(summary)

    return "\n".join(lines) + "\n"


def project_frame(frame: "FrameRecord", include_think: bool = True) -> str:
    """Project a FrameRecord into human-readable text.

    Section omission rules:
    - [think]   omitted if think is empty or include_think=False
    - [expect]  omitted if expect is empty
    - [stdout]  omitted if stdout is empty
    - [diff]    omitted if diff is empty
    - [error]   omitted if error is None
    - [verdict] omitted if verdict is None

    [operation] is always present.

    Args:
        frame: FrameRecord to project.
        include_think: Whether to include the [think] section.

    Returns:
        Formatted multi-line string ending with a newline.
    """
    lines: list[str] = []

    lines.append(f"── frame {frame.number} ──")

    if include_think and frame.pong.think:
        lines.append("[think]")
        lines.append(frame.pong.think)

    lines.append("[operation]")
    lines.append(frame.pong.action.operation)

    if frame.pong.action.expect:
        lines.append("[expect]")
        lines.append(frame.pong.action.expect)

    if frame.observation.stdout:
        lines.append("[stdout]")
        lines.append(frame.observation.stdout)

    if frame.observation.diff:
        lines.append("[diff]")
        lines.append(frame.observation.diff)

    if frame.observation.error is not None:
        lines.append("[error]")
        lines.append(frame.observation.error)

    if frame.observation.verdict is not None:
        verdict = frame.observation.verdict
        lines.append("[verdict]")
        summary = f"{verdict.passed}/{verdict.total} assertions passed"
        if verdict.failures:
            failure_parts = []
            for f in verdict.failures:
                failure_parts.append(f"  [{f.kind}] {f.assertion}: {f.message}")
            lines.append(summary)
            lines.extend(failure_parts)
        else:
            lines.append(summary)

    return "\n".join(lines) + "\n"


def render_frame_stream(ns: dict, budget_tokens: int) -> tuple[str, int]:
    """Render frame stream text, physically deleting the oldest frames when over budget.

    Unlike the old render trimming approach, this method directly modifies ns["_frame_log"] —
    deleted frames are unrecoverable (cold storage was already written to JSONL by FrameLogger
    at frame execution time).

    Args:
        ns:            Kernel namespace; reads and may modify _frame_log (list[dict]).
        budget_tokens: Upper limit on tokens available for the frame stream.

    Returns:
        (frame_stream_text, dropped_count) 2-tuple.
        frame_stream_text does not include the "══════ frame stream ══════" header
        (the caller renderer concatenates it).
    """
    frame_log = ns.get("_frame_log", [])
    if not frame_log:
        return "", 0

    rendered = [project_frame_dict(f) for f in frame_log]
    full_text = "\n\n".join(rendered)
    if estimate_tokens(full_text) <= budget_tokens:
        return full_text, 0

    return _hard_delete_and_render(frame_log, budget_tokens)


def _hard_delete_and_render(
    frame_log: list[dict], budget_tokens: int
) -> tuple[str, int]:
    """Physically delete the oldest frames until the frame stream is within budget. Retains at least 1 frame."""
    dropped = 0

    while len(frame_log) > 1:
        rendered = [project_frame_dict(f) for f in frame_log]
        text = "\n\n".join(rendered)
        if estimate_tokens(text) <= budget_tokens:
            break
        frame_log.pop(0)
        dropped += 1

    rendered = [project_frame_dict(f) for f in frame_log]
    result = "\n\n".join(rendered)
    if dropped > 0:
        result = f"[{dropped} earlier frame(s) dropped, cold storage intact]\n\n" + result
    return result, dropped
