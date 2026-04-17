"""protocol.py — v4 Cell Protocol data structures: Ping/Pong/FrameRecord and all sub-structures."""
#        Provides to_dict()/from_dict() serialization methods.
#        This is the single source of truth shared by all consumers of the Cell subsystem.
#
# Not responsible for: business logic, execution, network calls, rendering.
# Dependencies: standard library only (dataclasses, typing).

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

FRAME_SCHEMA_VERSION = 7


# ─────────────────────────────────────────────
# VerdictFailure
# ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class VerdictFailure:
    """A single prediction failure record.

    Attributes:
        kind: Failure type.
            "assertion_failed"    — assert expression evaluated to False.
            "expect_syntax_error" — expect code has a syntax error (Python SyntaxError).
            "expect_unsafe_error" — expect code contains disallowed syntax (AST allowlist check).
            "expect_runtime_error" — expect code raised a non-AssertionError exception at runtime.
        assertion: Code string of the original assert statement (decompiled from the AST node).
        message: Human-readable failure reason.
    """

    kind: Literal[
        "assertion_failed",
        "expect_syntax_error",
        "expect_unsafe_error",
        "expect_runtime_error",
    ]
    assertion: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict.

        Returns:
            Dict with keys: kind, assertion, message.
        """
        return {
            "kind": self.kind,
            "assertion": self.assertion,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "VerdictFailure":
        """Deserialize from a dict.

        Args:
            d: Dict with keys: kind, assertion, message.

        Returns:
            VerdictFailure instance.
        """
        return cls(
            kind=d["kind"],
            assertion=d["assertion"],
            message=d["message"],
        )


# ─────────────────────────────────────────────
# Verdict
# ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Verdict:
    """Prediction verification result.

    Invariant: total >= passed >= 0, len(failures) == total - passed.
    When expect is an empty string, the verdict field is None, not Verdict(total=0, ...).

    Attributes:
        total: Total number of assert statements in expect.
        passed: Number of assertions that passed.
        failures: Detailed records for each failed assertion, in the order they appear in expect.
    """

    total: int
    passed: int
    failures: tuple[VerdictFailure, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict.

        Returns:
            Dict with keys: total, passed, failures.
        """
        return {
            "total": self.total,
            "passed": self.passed,
            "failures": [f.to_dict() for f in self.failures],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Verdict":
        """Deserialize from a dict.

        Args:
            d: Dict with keys: total, passed, failures.

        Returns:
            Verdict instance.
        """
        return cls(
            total=d["total"],
            passed=d["passed"],
            failures=tuple(VerdictFailure.from_dict(f) for f in d["failures"]),
        )


# ─────────────────────────────────────────────
# Observation
# ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Observation:
    """The world's response to an action — all observable effects of an operation on the namespace.

    Attributes:
        stdout: print() output + the value of the last non-None expression (Jupyter style).
        diff: Namespace change record (+ appeared, - disappeared), git style.
        error: Traceback string if the operation raised an exception. None means no exception.
        verdict: Prediction verification result. None means no expect or the operation failed.
    """

    stdout: str
    diff: str
    error: str | None
    verdict: Verdict | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict.

        Returns:
            Dict with keys: stdout, diff, error, verdict (verdict value is null when None).
        """
        return {
            "stdout": self.stdout,
            "diff": self.diff,
            "error": self.error,
            "verdict": self.verdict.to_dict() if self.verdict is not None else None,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Observation":
        """Deserialize from a dict.

        Args:
            d: Dict with keys: stdout, diff, error, verdict.

        Returns:
            Observation instance.
        """
        verdict_data = d["verdict"]
        return cls(
            stdout=d["stdout"],
            diff=d["diff"],
            error=d["error"],
            verdict=Verdict.from_dict(verdict_data) if verdict_data is not None else None,
        )


# ─────────────────────────────────────────────
# Action
# ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Action:
    """The execution instruction part of Pong. operation + expect.

    Attributes:
        operation: Python code string to execute.
        expect: Assertion code string to verify after execution (may be empty).
    """

    operation: str
    expect: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict.

        Returns:
            Dict with keys: operation, expect.
        """
        return {"operation": self.operation, "expect": self.expect}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Action":
        """Deserialize from a dict.

        Args:
            d: Dict with keys operation and expect (missing keys default to empty string).

        Returns:
            Action instance.
        """
        return Action(operation=d.get("operation", ""), expect=d.get("expect", ""))


# ─────────────────────────────────────────────
# State
# ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class State:
    """Dynamic observation part of Ping. frame_stream + signals.

    Attributes:
        frame_stream: Historical frame summary text (rendered by Kernel).
        signals: Current system signal text (e.g. goal, vars, verdict, etc.).
    """

    frame_stream: str
    signals: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict.

        Returns:
            Dict with keys: frame_stream, signals.
        """
        return {"frame_stream": self.frame_stream, "signals": self.signals}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "State":
        """Deserialize from a dict.

        Args:
            d: Dict with keys frame_stream and signals (missing keys default to empty string).

        Returns:
            State instance.
        """
        return cls(frame_stream=d.get("frame_stream", ""), signals=d.get("signals", ""))


# ─────────────────────────────────────────────
# Ping
# ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Ping:
    """Perception signal sent by the system to the reasoner.

    Attributes:
        system_prompt: Quasi-static identity definition text.
        state: Dynamic observation part (frame stream + signals).
    """

    system_prompt: str   # Quasi-static: identity definition
    state: State         # Dynamic: frame stream + signals

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict.

        Returns:
            Dict with keys: system_prompt, state.
        """
        return {"system_prompt": self.system_prompt, "state": self.state.to_dict()}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Ping":
        """Deserialize from a dict.

        Args:
            d: Dict with keys system_prompt and state (missing keys default to empty string).

        Returns:
            Ping instance.
        """
        return cls(
            system_prompt=d.get("system_prompt", ""),
            state=State.from_dict(d.get("state", {})),
        )


# ─────────────────────────────────────────────
# Pong
# ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Pong:
    """Control signal sent by the reasoner to the system.

    Attributes:
        think: Reasoning process text (read-only; produces no side effects).
        action: Execution instruction (contains operation and expect; has side effects).
    """

    think: str           # Reasoning process (read-only)
    action: Action       # Execution instruction (has side effects)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict.

        Returns:
            Dict with keys: think, action.
        """
        return {"think": self.think, "action": self.action.to_dict()}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Pong":
        """Deserialize from a dict; compatible with the old flat format.

        Args:
            d: Dict with keys think and action; or old flat dict with operation/expect at the top level.

        Returns:
            Pong instance.
        """
        action_d = d.get("action", {})
        # Backward compat: old flat pong dict has no "action" key
        if not action_d and ("operation" in d or "expect" in d):
            action_d = {"operation": d.get("operation", ""), "expect": d.get("expect", "")}
        return Pong(think=d.get("think", ""), action=Action.from_dict(action_d))


# ─────────────────────────────────────────────
# FrameRecord
# ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FrameRecord:
    """Complete record of one frame — single source of truth.

    Attributes:
        number: Frame sequence number, starting from 1.
        ping: Perception input seen by the model for this frame (added in v6).
        pong: Parsed reasoning output (the LLM's Pong).
        observation: All observable effects of the operation on the namespace.
    """

    number: int
    ping: Ping
    pong: Pong
    observation: Observation

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict, including the schema_version field.

        Returns:
            Dict with keys: schema_version, number, ping, pong, observation.
        """
        return {
            "schema_version": FRAME_SCHEMA_VERSION,
            "number": self.number,
            "ping": self.ping.to_dict(),
            "pong": self.pong.to_dict(),
            "observation": self.observation.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FrameRecord":
        """Deserialize from a dict. Compatible with v5 (no ping field) and v6.

        Args:
            d: Dict with keys number, pong, observation; v6 additionally has a ping key.

        Returns:
            FrameRecord instance.
        """
        ping_data = d.get("ping")
        ping = (
            Ping.from_dict(ping_data)
            if ping_data is not None
            else Ping(system_prompt="", state=State(frame_stream="", signals=""))
        )
        return cls(
            number=d["number"],
            ping=ping,
            pong=Pong.from_dict(d.get("pong", {})),
            observation=Observation.from_dict(d.get("observation", {})),
        )


# ─────────────────────────────────────────────
# ErrorRecord
# ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ErrorRecord:
    """System error record. An element of the namespace `_errors` list.

    Attributes:
        type: Error type — "protocol" (API/parse failure), "runtime" (agent code exception),
              "builtin_restored" (protected key deleted then restored).
        message: Full error message.
        frame: Frame number when the error occurred.
        timestamp: time.time() when the error occurred.
    """

    type: str
    message: str
    frame: int
    timestamp: float

    def summary(self, max_len: int = 200) -> str:
        """Generate an error summary.

        Args:
            max_len: Truncation length for message.

        Returns:
            Formatted single-line summary.
        """
        msg = self.message[:max_len]
        if len(self.message) > max_len:
            msg += "..."
        return f"[F{self.frame}|{self.type}] {msg}"


# ─────────────────────────────────────────────
# StepResult
# ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class StepResult:
    """Return value of Cell.step().

    Attributes:
        protocol_error: When non-None, indicates the reason the frame was not committed.
    """

    protocol_error: str | None = None


@dataclass(frozen=True, slots=True)
class CompactionRecord:
    """Schema v1 compaction record — one summary of k frames or k lower-layer records.

    Fields mirror whitepaper §6.4.2. `layer` is the cold-zone index (0 = L_0).
    `compacted_at` is the frame number at which this record was produced.
    """

    range: tuple[int, int]
    intent: str
    operations: tuple[str, ...]
    outcomes: str
    artifacts: tuple[str, ...]
    notable: str
    layer: int
    compacted_at: int

    def to_dict(self) -> dict:
        return {
            "schema_version": FRAME_SCHEMA_VERSION,
            "range": list(self.range),
            "intent": self.intent,
            "operations": list(self.operations),
            "outcomes": self.outcomes,
            "artifacts": list(self.artifacts),
            "notable": self.notable,
            "layer": self.layer,
            "compacted_at": self.compacted_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CompactionRecord":
        return cls(
            range=tuple(d["range"]),
            intent=d["intent"],
            operations=tuple(d["operations"]),
            outcomes=d["outcomes"],
            artifacts=tuple(d["artifacts"]),
            notable=d["notable"],
            layer=d["layer"],
            compacted_at=d["compacted_at"],
        )


__all__ = [
    "FRAME_SCHEMA_VERSION",
    "Action", "State",
    "Ping", "Pong", "Observation", "FrameRecord", "StepResult",
    "Verdict", "VerdictFailure",
    "ErrorRecord",
    "CompactionRecord",
]
