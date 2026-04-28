# test_cell.py — Cell module tests (v4 Protocol)
#
# Strategy: mock cell._core.step (avoid real API calls); Kernel uses a real instance.
# Cell.step() returns StepResult(protocol_error=str|None).
# _core.step accepts a Ping (system perception) and returns Pong(think=str, action=Action(...)).
# _frame_stream stores frame dicts in hot zone (not FrameRecord instances).

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vessal.ark.shell.hull.cell import Cell
from vessal.ark.shell.hull.cell.protocol import (
    Action, Ping, Pong, State, StepResult,
)
from vessal.ark.shell.hull.cell.core.parser import parse_response


# ============================================================
# Helper functions
# ============================================================


def _make_cell(**kwargs) -> Cell:
    """Create a Cell; remaining args are passed through."""
    with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI"):
        return Cell(**kwargs)


def _make_pong(raw_text: str) -> Pong:
    """Construct a Pong from raw_text using the real parse_response (LLM response)."""
    return parse_response(raw_text)


def _set_responses(cell: Cell, raw_texts: list) -> None:
    """Configure _core.step to return (Pong, None, None) or raise exceptions in sequence.

    If a list element is an Exception instance, it is raised directly.
    If it is a str, parsing is attempted: success returns (Pong, None, None), failure raises ParseError.
    """
    from vessal.ark.shell.hull.cell.core.parser import ParseError as _ParseError

    def _build(item):
        if isinstance(item, Exception):
            return item  # Exception: will be raised by side_effect
        try:
            return (_make_pong(item), None, None)  # tuple: Core.step() return format
        except _ParseError as e:
            return e  # ParseError: will be raised by side_effect

    side_effects = [_build(t) for t in raw_texts]

    def _side_effect(*args, **kwargs):
        val = side_effects.pop(0)
        if isinstance(val, Exception):
            raise val
        return val  # returns (Pong, None, None) tuple

    cell._core.step = MagicMock(side_effect=_side_effect)


def _action(code: str) -> str:
    """Generate LLM response text containing an <action> tag."""
    return f"<action>{code}</action>"


def _action_with_expect(code: str, expect: str) -> str:
    """Generate LLM response text containing <action> and <expect> tags."""
    return f"<action>{code}</action><expect>{expect}</expect>"


# ============================================================
# Constructor tests
# ============================================================


class TestConstructor:
    """Constructor: default parameters, parameter pass-through, snapshot path."""

    def test_default_parameters(self):
        """Default parameter values are correct."""
        cell = _make_cell()
        assert cell.action_gate == "auto"
        assert cell.state_gate == "auto"

    def test_no_run_method(self):
        """Cell no longer has a run() method."""
        cell = _make_cell()
        assert not hasattr(cell, "run")

    def test_api_params_forwarded_to_core(self):
        """api_params are forwarded to Core."""
        cell = _make_cell(api_params={"temperature": 0.3, "max_tokens": 2048})
        assert cell._core._api_params["temperature"] == 0.3
        assert cell._core._api_params["max_tokens"] == 2048

    def test_default_api_params(self):
        """Default api_params include temperature and max_tokens."""
        cell = _make_cell()
        assert cell._core._api_params["temperature"] == 0.7
        assert cell._core._api_params["max_tokens"] == 4096

    def test_snapshot_path_forwarded(self, tmp_path):
        """restore_path is forwarded to Kernel — namespace is consistent when restored from snapshot."""
        cell1 = _make_cell()
        cell1.L["saved_var"] = 999
        snap = str(tmp_path / "snap.pkl")
        cell1.snapshot(snap)

        cell2 = _make_cell(restore_path=snap)
        assert cell2.L["saved_var"] == 999

    def test_ns_is_dict(self):
        """ns property exposes the namespace dict."""
        cell = _make_cell()
        assert isinstance(cell.L, dict)

    def test_ns_is_kernel_ns_reference(self):
        """ns property returns the same reference as Kernel namespace, not a copy."""
        cell = _make_cell()
        cell.L["injected"] = "hello"
        assert cell._kernel.L["injected"] == "hello"


# ============================================================
# step() basic behavior
# ============================================================


class TestStepBasic:
    """step() basic behavior: return type, StepResult fields."""

    def test_step_returns_step_result(self):
        """step() returns a StepResult instance."""
        cell = _make_cell()
        _set_responses(cell, [_action("x = 1")])
        result = cell.step()
        assert isinstance(result, StepResult)

    def test_successful_step_has_no_protocol_error(self):
        """Successful step: protocol_error is None."""
        cell = _make_cell()
        _set_responses(cell, [_action("x = 1")])
        result = cell.step()
        assert result.protocol_error is None

    def test_step_calls_core(self):
        """step() calls Core.step()."""
        cell = _make_cell()
        _set_responses(cell, [_action("x = 1")])
        cell.step()
        assert cell._core.step.called

    def test_step_executes_action(self):
        """step() executes the code returned by Core — new variable appears in namespace."""
        cell = _make_cell()
        _set_responses(cell, [_action("step_result = 42")])
        cell.step()
        assert cell.L.get("step_result") == 42

    def test_step_does_not_modify_lifecycle_vars(self):
        """step() does not modify _sleeping/_next_wake or G['_system']._wake_reason."""
        cell = _make_cell()
        _set_responses(cell, [_action("x = 1")])
        cell.L["_sleeping"] = False
        cell.G["_system"].wake("test_wake")
        cell.L["_next_wake"] = None
        cell.step()
        assert cell.L["_sleeping"] is False
        assert cell.G["_system"]._wake_reason == "test_wake"
        assert cell.L["_next_wake"] is None

    def test_step_accepts_tracer_none(self):
        """step(tracer=None) runs normally without error."""
        cell = _make_cell()
        _set_responses(cell, [_action("x = 1")])
        cell.step(tracer=None)
        assert cell.L.get("x") == 1

    def test_step_accepts_tracer_mock(self):
        """step(tracer=mock_tracer) runs without error and tracer.start/end are called."""
        cell = _make_cell()
        _set_responses(cell, [_action("x = 1")])
        mock_tracer = MagicMock()
        cell.step(tracer=mock_tracer)
        assert mock_tracer.start.called
        assert mock_tracer.end.called


# ============================================================
# Frame number increment
# ============================================================


class TestFrameNumber:
    """Frame number increment behavior."""

    def test_frame_increments_on_success(self):
        """Frame number increments after a valid action."""
        cell = _make_cell()
        _set_responses(cell, [_action("x = 1")])
        before = cell.L["_frame"]
        cell.step()
        assert cell.L["_frame"] == before + 1

    def test_frame_increments_correctly_multiple_steps(self):
        """Multi-frame increment: frame number increases by 1 per successful step."""
        cell = _make_cell()
        _set_responses(cell, [_action("x = 1"), _action("y = 2")])
        start = cell.L["_frame"]
        cell.step()
        cell.step()
        assert cell.L["_frame"] == start + 2

    def test_parse_error_no_frame_increment(self):
        """Parse failure (missing <action> tag): frame number does not increment."""
        cell = _make_cell()
        _set_responses(cell, ["no action tag here"])
        before = cell.L["_frame"]
        cell.step()
        assert cell.L["_frame"] == before


# ============================================================
# Protocol error paths
# ============================================================


class TestProtocolErrors:
    """Protocol error paths: parse failure, gate block, Core exception."""

    def test_missing_action_tag_no_frame_committed(self):
        """Missing <action> tag → protocol_error is not None."""
        cell = _make_cell()
        _set_responses(cell, ["no action tag here"])
        result = cell.step()
        assert result.protocol_error is not None

    def test_core_exception_no_frame_committed(self):
        """Core raises exception → protocol_error is not None."""
        cell = _make_cell()
        _set_responses(cell, [Exception("API error")])
        result = cell.step()
        assert result.protocol_error is not None

    def test_core_exception_no_frame_increment(self):
        """Core raises exception → frame number does not increment."""
        cell = _make_cell()
        _set_responses(cell, [Exception("API error")])
        before = cell.L["_frame"]
        cell.step()
        assert cell.L["_frame"] == before

    def test_action_gate_blocked_no_frame_committed(self):
        cell = _make_cell(action_gate="safe")
        cell._action_gate.add_rule("block_all", lambda a: "blocked for test")
        _set_responses(cell, [_action("x = 1")])
        result = cell.step()
        assert result.protocol_error == "Action gate blocked"

    def test_action_gate_blocked_no_frame_increment(self):
        """action gate block → frame number does not increment."""
        cell = _make_cell(action_gate="safe")
        cell._action_gate.add_rule("block_all", lambda a: "blocked for test")
        _set_responses(cell, [_action("x = 1")])
        before = cell.L["_frame"]
        cell.step()
        assert cell.L["_frame"] == before


# ============================================================
# Execution result recording
# ============================================================


# ============================================================
# _commit_frame writes to frame_log (SQLite)
# ============================================================


class TestCommitFrame:
    """_commit_frame: mirror variable write."""

    def test_verdict_mirror_variable_updated(self):
        """After a successful step, ns["verdict"] is updated (mirror variable, no underscore)."""
        cell = _make_cell()
        _set_responses(cell, [_action("x = 1")])
        cell.step()
        # verdict should be written (value may be None when no expect, but key exists)
        assert "verdict" in cell.L

    def test_verdict_mirror_set_after_expect(self):
        """After expect passes, ns["verdict"] is a Verdict object."""
        cell = _make_cell()
        _set_responses(cell, [_action_with_expect("x = 5", "assert x == 5")])
        cell.step()
        from vessal.ark.shell.hull.cell.protocol import Verdict
        assert isinstance(cell.L["verdict"], Verdict)


# ============================================================
# _update_runtime_vars
# ============================================================


# ============================================================
# Gate tests
# ============================================================


class TestGates:
    """Gates: default values, auto mode passthrough."""

    def test_state_gate_default_is_auto(self):
        """state_gate default value is 'auto'."""
        cell = _make_cell()
        assert cell.state_gate == "auto"

    def test_action_gate_default_is_auto(self):
        """action_gate default value is 'auto'."""
        cell = _make_cell()
        assert cell.action_gate == "auto"

    def test_state_gate_auto_passthrough(self):
        """auto mode: state is not blocked, step completes normally."""
        cell = _make_cell()
        cell.state_gate = "auto"
        _set_responses(cell, [_action("x = 1")])
        cell.step()
        assert cell.L.get("x") == 1

    def test_action_gate_auto_passthrough(self):
        """auto mode: action is not blocked, step completes normally."""
        cell = _make_cell()
        cell.action_gate = "auto"
        _set_responses(cell, [_action("x = 1")])
        cell.step()
        assert cell.L.get("x") == 1

    def test_step_applies_state_gate(self):
        """step() passes through state_gate internally (auto mode allows all)."""
        cell = _make_cell()
        _set_responses(cell, [_action('sleep()')])
        cell.state_gate = "auto"
        cell.step()
        assert cell.L["_sleeping"] is True

    def test_step_applies_action_gate(self):
        """step() passes through action_gate internally (auto mode allows all)."""
        cell = _make_cell()
        _set_responses(cell, [_action('sleep()')])
        cell.action_gate = "auto"
        cell.step()
        assert cell.L["_sleeping"] is True


# ============================================================
# Snapshot and restore tests
# ============================================================


class TestSnapshotRestore:
    """snapshot/restore: state serialization and deserialization."""

    def test_snapshot_creates_file(self, tmp_path):
        """snapshot(path) creates a file at the specified path."""
        cell = _make_cell()
        cell.L["data"] = [1, 2, 3]
        path = str(tmp_path / "snap.pkl")
        cell.snapshot(path)
        assert Path(path).exists()

    def test_restore_recovers_state(self, tmp_path):
        """restore(path) recovers namespace from snapshot."""
        cell1 = _make_cell()
        cell1.L["data"] = [1, 2, 3]
        path = str(tmp_path / "snap.pkl")
        cell1.snapshot(path)

        cell2 = _make_cell()
        cell2.restore(path)
        assert cell2.L["data"] == [1, 2, 3]

    def test_snapshot_via_snapshot_path(self, tmp_path):
        """restore_path constructor parameter is equivalent to restore() — namespace is recovered."""
        cell1 = _make_cell()
        _set_responses(cell1, [_action("saved_var = 999")])
        cell1.step()

        snap = str(tmp_path / "test_snap.pkl")
        cell1.snapshot(snap)

        cell2 = _make_cell(restore_path=snap)
        assert cell2.L["saved_var"] == 999


# ============================================================
# v5 Protocol: ping/pong properties
# ============================================================


class TestPingPongProperties:
    """v5 ping/pong cached properties."""

    def test_cell_pong_property_initially_none(self):
        """Before first step(), cell.pong is None."""
        cell = _make_cell()
        assert cell.pong is None

    def test_cell_pong_property_after_step(self):
        """After step(), cell.pong is a Pong."""
        cell = _make_cell()
        _set_responses(cell, [_action("x = 1")])
        result = cell.step()
        if result.protocol_error is None:
            assert cell.pong is not None
            assert isinstance(cell.pong, Pong)

    def test_cell_ping_property_initially_none(self):
        """Before first step(), cell.ping is None."""
        cell = _make_cell()
        assert cell.ping is None

    def test_cell_ping_property_after_step(self):
        """After step(), cell.ping is a Ping."""
        cell = _make_cell()
        _set_responses(cell, [_action("x = 1")])
        result = cell.step()
        if result.protocol_error is None:
            assert cell.ping is not None
            assert isinstance(cell.ping, Ping)

    def test_step_result_has_only_protocol_error(self):
        """StepResult has protocol_error only, not frame or state."""
        cell = _make_cell()
        _set_responses(cell, [_action("x = 1")])
        result = cell.step()
        assert hasattr(result, "protocol_error")
        assert not hasattr(result, "state")
        assert not hasattr(result, "frame")

    def test_error_path_pong_unchanged(self):
        """When Core raises, cell.pong retains previous value."""
        cell = _make_cell()
        # First step succeeds
        _set_responses(cell, [_action("x = 1")])
        result1 = cell.step()
        pong_after_success = cell.pong
        # Second step fails (mock raises)
        _set_responses(cell, [Exception("API error")])
        result2 = cell.step()
        assert result2.protocol_error is not None
        assert cell.pong is pong_after_success  # unchanged


# ============================================================
# Fresh Ping per frame
# ============================================================


class TestFreshPingPerFrame:
    """Every step() must produce a fresh Ping via prepare(), not reuse a cached one."""

    def test_signal_injected_between_frames_is_visible(self):
        """A BaseSkill added to namespace between step() calls appears in the next Ping.

        This verifies that step() calls prepare() every frame, not just the first.
        If Ping were cached from the previous frame, this new signal would be invisible.
        """
        from vessal.skills._base import BaseSkill
        cell = _make_cell()

        # First step — establish baseline
        _set_responses(cell, [_action("x = 1"), _action("y = 2")])
        result1 = cell.step()
        assert result1.protocol_error is None

        # Inject a BaseSkill into namespace BETWEEN frames
        class _TestSkill(BaseSkill):
            name = "test_skill"
            description = "test"

            def signal_update(self) -> None:
                self.signal = {"status": "signal_was_seen"}

        cell.L["_test_signal_source"] = _TestSkill()

        # Second step — the fresh prepare() must pick up the new signal
        result2 = cell.step()
        assert result2.protocol_error is None

        # Verify the Ping used for the second step contained the new signal
        # cell.ping is set at the start of step() by prepare()
        assert cell.ping is not None
        signals = cell.ping.state.signals
        assert any(
            isinstance(payload, dict) and payload.get("status") == "signal_was_seen"
            for payload in signals.values()
        )


# ============================================================
# Real token data written to namespace
# ============================================================


class TestRealTokenPassthrough:
    """Cell.step() writes real token data returned by Core to namespace."""

    def test_actual_tokens_written_to_ns(self):
        cell = _make_cell()
        pong = _make_pong(_action("x = 1"))
        cell._core.step = MagicMock(return_value=(pong, 5000, 200))
        cell.step()
        assert cell.L["_actual_tokens_in"] == 5000
        assert cell.L["_actual_tokens_out"] == 200

    def test_no_usage_leaves_estimated_context_pct(self):
        cell = _make_cell()
        pong = _make_pong(_action("x = 1"))
        cell._core.step = MagicMock(return_value=(pong, None, None))
        cell.step()
        assert cell.L.get("_actual_tokens_in") is None

