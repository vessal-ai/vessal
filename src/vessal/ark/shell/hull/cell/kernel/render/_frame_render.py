"""_frame_render.py — Frame stream rendering (FrameRecord projection + budget trimming).

render_frame_stream(ns, budget_tokens) -> tuple[str, int]
    Render the frame stream text from FrameStream (cold zone + hot buckets).
    Drops oldest hot buckets when over budget; cold zone is never dropped.
    Returns (frame_stream_text, dropped_count).
    frame_stream_text does not include the "══════ frame stream ══════" header
    (that is concatenated by renderer.py).

project_frame_dict(frame_dict, include_think) -> str
    Project a frame dict into a frame stream text block.

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
    """Render cold zone + hot buckets, trimming oldest hot buckets to budget.

    Cold zone is never dropped — if cold alone exceeds budget, a warning line
    is prepended and the full cold text returned. Returns (text, dropped_count)
    where dropped_count = number of hot frames removed to fit budget.

    Args:
        ns:            Kernel namespace; reads ns["_frame_stream"] (FrameStream).
        budget_tokens: Upper limit on tokens available for the frame stream.

    Returns:
        (frame_stream_text, dropped_count) 2-tuple.
        frame_stream_text does not include the "══════ frame stream ══════" header.
    """
    from vessal.ark.shell.hull.cell.kernel.render._cold_render import render_cold_zone

    fs = ns.get("_frame_stream")
    if fs is None:
        return "", 0
    view = fs.project_render()
    cold_text = render_cold_zone(view["cold"])

    # Hot buckets oldest-first (B_4..B_0); each bucket has strip level already applied
    hot_texts: list[str] = []
    hot_counts: list[int] = []
    for bucket in view["hot"]:
        frames_text = "\n\n".join(project_frame_dict(f) for f in bucket)
        hot_texts.append(frames_text)
        hot_counts.append(len(bucket))

    full_hot = "\n\n".join(t for t in hot_texts if t)
    if cold_text and full_hot:
        combined = cold_text + "\n\n" + full_hot
    elif full_hot:
        combined = full_hot
    else:
        combined = cold_text

    if estimate_tokens(combined) <= budget_tokens:
        return combined, 0

    # Over budget: flatten hot frames oldest-first, drop from front until within budget (keep >= 1).
    dropped = 0
    hot_frames: list[dict] = []
    for bucket in view["hot"]:
        hot_frames.extend(bucket)

    while len(hot_frames) > 1:
        candidate_hot = "\n\n".join(project_frame_dict(f) for f in hot_frames)
        full = (cold_text + "\n\n" + candidate_hot) if (cold_text and candidate_hot) else candidate_hot
        if estimate_tokens(full) <= budget_tokens:
            break
        hot_frames.pop(0)
        dropped += 1

    full_hot = "\n\n".join(project_frame_dict(f) for f in hot_frames)
    combined = (cold_text + "\n\n" + full_hot) if (cold_text and full_hot) else (full_hot or cold_text)
    if dropped > 0:
        combined = f"[{dropped} hot frame(s) dropped over budget, cold intact]\n\n" + combined
    return combined, dropped
