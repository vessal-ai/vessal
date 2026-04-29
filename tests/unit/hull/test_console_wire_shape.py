"""Hull's console wire shape exposes new verdict and diff structures."""
from __future__ import annotations

import json

from vessal.ark.shell.hull.cell.protocol import (
    Entry, FrameContent, FrameStream,
)


def test_wire_shape_has_single_verdict_dict_not_split():
    """The flat wire shape projects verdict as a single dict, not split verdict_value/verdict_error."""
    fs = FrameStream(entries=[
        Entry(layer=0, n_start=2, n_end=2, content=FrameContent(
            think="t", operation="x = 1", expect="assert x == 1",
            observation={
                "stdout": "", "stderr": "",
                "diff": [{"op": "+", "name": "x", "type": "int"}],
                "error": None,
            },
            verdict={"total": 1, "passed": 1, "failures": []},
            signals={},
        )),
    ])

    flat = []
    for entry in fs.entries:
        if entry.layer != 0:
            continue
        c = entry.content
        flat.append({
            "n": entry.n_start,
            "obs_diff_json": json.dumps(c.observation.get("diff") or []),
            "verdict": c.verdict,
        })

    assert len(flat) == 1
    assert flat[0]["obs_diff_json"] == '[{"op": "+", "name": "x", "type": "int"}]'
    assert flat[0]["verdict"] == {"total": 1, "passed": 1, "failures": []}
    assert "verdict_value" not in flat[0]
    assert "verdict_error" not in flat[0]


def test_wire_shape_diff_fallback_is_list_not_dict():
    """obs_diff_json falls back to [] (list), not {} (dict)."""
    fs = FrameStream(entries=[
        Entry(layer=0, n_start=1, n_end=1, content=FrameContent(
            think="t", operation="pass", expect="",
            observation={"stdout": "", "stderr": "", "diff": None, "error": None},
            verdict=None,
            signals={},
        )),
    ])

    flat = []
    for entry in fs.entries:
        if entry.layer != 0:
            continue
        c = entry.content
        flat.append({
            "obs_diff_json": json.dumps(c.observation.get("diff") or []),
            "verdict": c.verdict,
        })

    assert flat[0]["obs_diff_json"] == "[]"
    assert flat[0]["verdict"] is None


def test_wire_shape_skips_non_layer0_entries():
    """Non-layer-0 entries (summaries) are excluded from the flat projection."""
    fs = FrameStream(entries=[
        Entry(layer=1, n_start=1, n_end=3, content=FrameContent(
            think="summary", operation="", expect="",
            observation={"stdout": "", "stderr": "", "diff": [], "error": None},
            verdict=None,
            signals={},
        )),
        Entry(layer=0, n_start=4, n_end=4, content=FrameContent(
            think="real", operation="y = 2", expect="assert y == 2",
            observation={"stdout": "", "stderr": "", "diff": [], "error": None},
            verdict={"total": 1, "passed": 1, "failures": []},
            signals={},
        )),
    ])

    flat = [
        {"n": e.n_start, "verdict": e.content.verdict}
        for e in fs.entries
        if e.layer == 0
    ]

    assert len(flat) == 1
    assert flat[0]["n"] == 4
