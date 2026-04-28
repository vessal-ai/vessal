"""tests/unit/test_gate.py — ActionGate / StateGate unit tests."""

from __future__ import annotations

import pytest

from vessal.ark.shell.hull.cell.gate import ActionGate, ActionGateResult, StateGate, StateGateResult
from vessal.ark.shell.hull.cell.protocol import FrameStream


# ────────────────────────────────────────────── ActionGate


class TestActionGateAutoMode:
    def test_auto_allows_any_action(self) -> None:
        gate = ActionGate(mode="auto")
        result = gate.check("shutil.rmtree('/')")
        assert result.allowed is True

    def test_auto_returns_result_with_action(self) -> None:
        gate = ActionGate(mode="auto")
        code = "x = 1"
        result = gate.check(code)
        assert result.action == code
        assert result.reason == ""


class TestActionGateSafeMode:
    def test_safe_blocks_dangerous_rm(self) -> None:
        gate = ActionGate(mode="safe")
        result = gate.check("import shutil; shutil.rmtree('/')")
        assert result.allowed is False
        assert "dangerous_rm" in result.reason

    def test_safe_blocks_system_path_write(self) -> None:
        gate = ActionGate(mode="safe")
        result = gate.check("open('/etc/passwd', 'w').write('x')")
        assert result.allowed is False
        assert "system_path_write" in result.reason

    def test_safe_allows_normal_code(self) -> None:
        gate = ActionGate(mode="safe")
        result = gate.check("x = [1, 2, 3]\nprint(x)")
        assert result.allowed is True

    def test_human_mode_behaves_like_safe(self) -> None:
        gate = ActionGate(mode="human")
        result = gate.check("import shutil; shutil.rmtree('/')")
        assert result.allowed is False


class TestActionGateCustomRules:
    def test_add_rule_is_called(self) -> None:
        gate = ActionGate(mode="safe")
        gate.add_rule("no_print", lambda a: "print not allowed" if "print(" in a else None)
        result = gate.check("print('hello')")
        assert result.allowed is False
        assert "no_print" in result.reason

    def test_remove_rule_stops_blocking(self) -> None:
        gate = ActionGate(mode="safe")
        gate.add_rule("no_print", lambda a: "print not allowed" if "print(" in a else None)
        gate.remove_rule("no_print")
        result = gate.check("print('hello')")
        assert result.allowed is True

    def test_rule_exception_does_not_crash(self) -> None:
        gate = ActionGate(mode="safe")
        gate.add_rule("bad_rule", lambda a: 1 / 0)  # type: ignore[return-value]
        result = gate.check("x = 1")
        # bad_rule raises but gate continues and allows
        assert result.allowed is True


# ────────────────────────────────────────────── StateGate


class TestStateGateAutoMode:
    def test_auto_allows_any_state(self) -> None:
        gate = StateGate(mode="auto")
        result = gate.check(FrameStream(entries=[]))
        assert result.allowed is True

    def test_auto_returns_frame_stream_unchanged(self) -> None:
        gate = StateGate(mode="auto")
        fs = FrameStream(entries=[])
        result = gate.check(fs)
        assert result.frame_stream is fs


class TestStateGateSafeMode:
    def test_safe_with_no_rules_allows_all(self) -> None:
        # StateGate safe mode has no builtin rules currently
        gate = StateGate(mode="safe")
        result = gate.check(FrameStream(entries=[]))
        assert result.allowed is True

    def test_add_rule_blocks(self) -> None:
        gate = StateGate(mode="safe")
        gate.add_rule("no_entries", lambda fs: "empty stream" if not fs.entries else None)
        result = gate.check(FrameStream(entries=[]))
        assert result.allowed is False
        assert "no_entries" in result.reason

    def test_remove_rule_stops_blocking(self) -> None:
        gate = StateGate(mode="safe")
        gate.add_rule("no_entries", lambda fs: "empty stream" if not fs.entries else None)
        gate.remove_rule("no_entries")
        result = gate.check(FrameStream(entries=[]))
        assert result.allowed is True


# ────────────────────────────────────────────── Result dataclass


class TestGateResult:
    def test_action_gate_result_defaults(self) -> None:
        r = ActionGateResult(allowed=True, action="x = 1")
        assert r.reason == ""

    def test_state_gate_result_defaults(self) -> None:
        r = StateGateResult(allowed=True, frame_stream=FrameStream(entries=[]))
        assert r.reason == ""

    def test_action_gate_result_blocked(self) -> None:
        r = ActionGateResult(allowed=False, action="rm -rf /", reason="[dangerous_rm] bad")
        assert r.allowed is False
        assert "dangerous_rm" in r.reason
