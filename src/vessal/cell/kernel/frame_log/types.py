"""types.py — Data shapes the writer accepts. Dataclasses, no logic.

See docs/architecture/kernel/04-frame-log.md §4.4 / §4.5 for field semantics.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ErrorOnSource:
    """One error row to insert into the errors table.

    Attributes:
        source: 'operation' | 'expect' | 'signal_update'.
        source_detail: var_name for signal_update; None otherwise.
        format_text: "".join(traceback.TracebackException.format()) text.
    """

    source: str
    source_detail: str | None
    format_text: str


@dataclass(frozen=True, slots=True)
class SignalRow:
    """One row for the signals table. Mutually exclusive: payload_json XOR error.

    Attributes:
        class_name: Skill class name (e.g., 'ChatSkill').
        var_name: variable name in G or L (e.g., 'chat_alice').
        scope: 'G' or 'L'.
        payload_json: JSON-encoded skill.signal dict (when signal_update succeeded).
        error: ErrorOnSource (when signal_update raised).
    """

    class_name: str
    var_name: str
    scope: str
    payload_json: str | None = None
    error: ErrorOnSource | None = None


@dataclass(frozen=True, slots=True)
class FrameWriteSpec:
    """Everything FrameLog.write_frame() needs to persist one layer=0 frame.

    Attributes:
        n: Frame number (used as both n_start and n_end for layer=0).
        pong_think / pong_operation / pong_expect: LLM output text. May be empty strings.
        obs_stdout / obs_stderr: captured streams.
        obs_diff_json: JSON-encoded namespace diff (list[{op,name,type}]).
        operation_error: error from running pong.operation (None if succeeded; at most one).
        verdict_value: JSON-encoded Verdict.to_dict() (None if expect was empty / first frame).
        verdict_errors: per-assert errors from running pong.expect (empty list if no Python
                        exception fired; one row per ExpectSyntaxError/ExpectRuntimeError).
        signals: list of SignalRow, one per Skill instance scanned this frame.
    """

    n: int
    pong_think: str
    pong_operation: str
    pong_expect: str
    obs_stdout: str
    obs_stderr: str
    obs_diff_json: str
    operation_error: ErrorOnSource | None
    verdict_value: str | None
    verdict_errors: list[ErrorOnSource] = field(default_factory=list)
    signals: list[SignalRow] = field(default_factory=list)
