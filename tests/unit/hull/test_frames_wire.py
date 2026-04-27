"""test_frames_wire.py — Hull.frames() emits flat wire shape (PR 1c contract)."""
from __future__ import annotations

import os

import pytest


@pytest.fixture
def hull(tmp_path):
    """Minimal Hull for wire-shape tests."""
    (tmp_path / "hull.toml").write_text(
        '[agent]\nname = "test"\nlanguage = "en"\n'
        '[cell]\nmax_frames = 5\n'
        '[hull]\nskills = []\nskill_paths = []\n'
    )
    (tmp_path / ".env").write_text("OPENAI_API_KEY=test-key\n")
    os.chdir(tmp_path)
    from vessal.ark.shell.hull.hull import Hull
    return Hull(str(tmp_path))


def _seed_one_frame(hull):
    """Push one synthetic dict-shaped frame into the hot zone."""
    fs = hull._cell.get("_frame_stream")
    fs.commit_frame({
        "schema_version": 7,
        "number": 42,
        "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
        "pong": {
            "think": "thought",
            "action": {"operation": "x = 1", "expect": "assert x == 1"},
        },
        "observation": {
            "stdout": "out",
            "diff": "[+x]",
            "error": None,
            "verdict": None,
        },
    })


def test_frames_endpoint_returns_flat_shape(hull):
    _seed_one_frame(hull)
    status, data = hull.handle("GET", "/frames", None)
    assert status == 200
    frames = data["frames"]
    assert len(frames) == 1
    f = frames[0]
    assert f["n"] == 42
    assert f["pong_think"] == "thought"
    assert f["pong_operation"] == "x = 1"
    assert f["pong_expect"] == "assert x == 1"
    assert f["obs_stdout"] == "out"
    assert f["obs_diff_json"] == "[+x]"
    assert f["obs_error"] is None
    assert f["verdict_value"] is None
    assert f["verdict_error"] is None
    assert f["signals"] == []
    assert f["layer"] == 0
    assert f["n_start"] == 42
    assert f["n_end"] == 42


def test_frames_endpoint_omits_legacy_nested_keys(hull):
    _seed_one_frame(hull)
    status, data = hull.handle("GET", "/frames", None)
    f = data["frames"][0]
    assert "number" not in f
    assert "pong" not in f
    assert "observation" not in f


def test_frames_after_filters_by_n(hull):
    fs = hull._cell.get("_frame_stream")
    for n in (1, 2, 3):
        fs.commit_frame({
            "schema_version": 7,
            "number": n,
            "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
            "pong": {"think": "", "action": {"operation": "", "expect": ""}},
            "observation": {"stdout": "", "diff": "", "error": None, "verdict": None},
        })
    status, data = hull.handle("GET", "/frames?after=1", None)
    assert status == 200
    ns = [f["n"] for f in data["frames"]]
    assert ns == [2, 3]
