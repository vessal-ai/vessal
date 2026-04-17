"""_strip.py — Mechanical stripping for hot-zone buckets B_0..B_4.

Each level removes one more field relative to the level below. Zero LLM cost;
pure dict transformation. Called by FrameStream.project() when rendering hot buckets.
"""
from __future__ import annotations

import copy


_EMPTY_VERDICT = {"total": 0, "passed": 0, "failures": []}


def strip_frame(frame: dict, level: int) -> dict:
    """Return a stripped copy of a frame dict for rendering at bucket level B_level.

    Level 0: identity (B_0 raw).
    Level 1: drop pong.think (B_1 −think).
    Level 2: also drop ping.state.signals (B_2 −signals).
    Level 3: also drop pong.action.expect (B_3 −expect).
    Level 4: also drop observation.{stdout, diff, error, verdict} (B_4 −obs).

    Raises:
        ValueError: if level is outside 0..4.
    """
    if level < 0 or level > 4:
        raise ValueError(f"strip level must be in 0..4, got {level}")
    if level == 0:
        return frame
    out = copy.deepcopy(frame)
    if level >= 1:
        out["pong"]["think"] = ""
    if level >= 2:
        out["ping"]["state"]["signals"] = ""
    if level >= 3:
        out["pong"]["action"]["expect"] = ""
    if level >= 4:
        obs = out["observation"]
        obs["stdout"] = ""
        obs["diff"] = ""
        obs["error"] = ""
        obs["verdict"] = dict(_EMPTY_VERDICT)
    return out
