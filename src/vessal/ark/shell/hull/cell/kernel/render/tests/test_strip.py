from __future__ import annotations

import pytest

from vessal.ark.shell.hull.cell.kernel.render._strip import strip_frame


def _fake_frame(number: int = 1) -> dict:
    return {
        "schema_version": 7,
        "number": number,
        "ping": {
            "system_prompt": "sys",
            "state": {"frame_stream": "...", "signals": "══ sig ══\nbody"},
        },
        "pong": {"think": "reasoning here", "action": {"operation": "print(1)", "expect": "1\n"}},
        "observation": {"stdout": "1\n", "diff": "", "error": "", "verdict": {"total": 0, "passed": 0, "failures": []}},
    }


def test_strip_level_0_is_identity():
    f = _fake_frame()
    assert strip_frame(f, 0) == f


def test_strip_level_1_removes_think():
    f = _fake_frame()
    out = strip_frame(f, 1)
    assert out["pong"]["think"] == ""
    assert out["pong"]["action"] == f["pong"]["action"]


def test_strip_level_2_also_removes_signals():
    f = _fake_frame()
    out = strip_frame(f, 2)
    assert out["pong"]["think"] == ""
    assert out["ping"]["state"]["signals"] == ""


def test_strip_level_3_also_removes_expect():
    f = _fake_frame()
    out = strip_frame(f, 3)
    assert out["pong"]["action"]["expect"] == ""


def test_strip_level_4_also_removes_observation():
    f = _fake_frame()
    out = strip_frame(f, 4)
    assert out["observation"]["stdout"] == ""
    assert out["observation"]["diff"] == ""
    assert out["observation"]["error"] == ""
    assert out["observation"]["verdict"] == {"total": 0, "passed": 0, "failures": []}


@pytest.mark.parametrize("level", [-1, 5, 100])
def test_strip_invalid_level_raises(level):
    with pytest.raises(ValueError):
        strip_frame(_fake_frame(), level)
