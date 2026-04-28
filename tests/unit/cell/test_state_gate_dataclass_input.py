"""test_state_gate_dataclass_input.py — StateGate consumes FrameStream dataclass."""
from __future__ import annotations

from vessal.ark.shell.hull.cell.gate.state_gate import StateGate
from vessal.ark.shell.hull.cell.protocol import (
    Entry, FrameContent, FrameStream,
)


def _make_gate(mode: str = "auto") -> StateGate:
    return StateGate(mode=mode)


def test_state_gate_check_accepts_framestream():
    fs = FrameStream(entries=[
        Entry(layer=0, n_start=1, n_end=1, content=FrameContent(
            think="", operation="x = 1", expect="True",
            observation={"stdout": "", "stderr": "", "diff": {}, "error": None},
            verdict=None, signals={},
        )),
    ])
    gate = _make_gate()
    result = gate.check(fs)
    assert result is not None


def test_state_gate_check_accepts_empty_framestream():
    gate = _make_gate()
    result = gate.check(FrameStream(entries=[]))
    assert result is not None
    assert result.allowed


def test_state_gate_check_auto_mode_always_allowed():
    gate = _make_gate(mode="auto")
    result = gate.check(FrameStream(entries=[]))
    assert result.allowed
    assert result.frame_stream.entries == []


def test_state_gate_check_safe_mode_no_rules_allowed():
    gate = _make_gate(mode="safe")
    fs = FrameStream(entries=[])
    result = gate.check(fs)
    assert result.allowed


def test_state_gate_check_safe_mode_rule_can_block():
    gate = _make_gate(mode="safe")
    gate.add_rule("block_all", lambda fs: "blocked by test")
    result = gate.check(FrameStream(entries=[]))
    assert not result.allowed
    assert "block_all" in result.reason


def test_state_gate_result_holds_framestream():
    gate = _make_gate()
    fs = FrameStream(entries=[])
    result = gate.check(fs)
    assert result.frame_stream is fs
