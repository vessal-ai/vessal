"""protocol.py — v4 Cell Protocol data structures: Ping/Pong/FrameRecord and all sub-structures."""
#        Provides to_dict()/from_dict() serialization methods.
#        This is the single source of truth shared by all consumers of the Cell subsystem.
#
# Not responsible for: business logic, execution, network calls, rendering.
# Dependencies: standard library only (dataclasses, typing).

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Union

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
# FrameStream (Spec §4.8)
# ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FrameContent:
    """Spec §4.8 layer=0 content — flat fields mirroring frame_content table."""
    think: str
    operation: str
    expect: str
    observation: dict        # {"stdout","stderr","diff","error"}
    verdict: dict | None     # {"value","error"} or None
    signals: dict            # {(class_name, var_name, scope): payload}


@dataclass(frozen=True, slots=True)
class SummaryContent:
    """Spec §4.8 layer>=1 content — opaque YAML body."""
    schema_version: int
    body: str


@dataclass(frozen=True, slots=True)
class Entry:
    """Spec §4.2 — (layer, n_start, n_end, content)."""
    layer: int
    n_start: int
    n_end: int
    content: Union[FrameContent, SummaryContent]


@dataclass(frozen=True, slots=True)
class FrameStream:
    """Spec §4.8 — single ordered list, layer DESC + n_start ASC."""
    entries: list[Entry]


# ─────────────────────────────────────────────
# State
# ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class State:
    """Spec §4.8 dynamic perceptual state. Kernel populates with dataclass +
    dict; Core composer stringifies before LLM call.

    Attributes:
        frame_stream: FrameStream dataclass (visible Entry list per spec §4.10).
        signals:      dict[(class_name, var_name, scope), payload_dict] from
                      L["signals"] (spec §6 + §4.4).
    """

    frame_stream: "FrameStream"
    signals: dict

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_stream": _framestream_to_dict(self.frame_stream),
            "signals": {
                "::".join(k): v for k, v in self.signals.items()
            },
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "State":
        fs_data = d.get("frame_stream", {"entries": []})
        signals_data = d.get("signals", {})
        return cls(
            frame_stream=_framestream_from_dict(fs_data),
            signals={tuple(k.split("::")): v for k, v in signals_data.items()},
        )


def _framestream_to_dict(fs: "FrameStream") -> dict:
    return {
        "entries": [
            {
                "layer": e.layer,
                "n_start": e.n_start,
                "n_end": e.n_end,
                "content": _content_to_dict(e.content),
            }
            for e in fs.entries
        ],
    }


def _content_to_dict(content) -> dict:
    if isinstance(content, FrameContent):
        return {
            "kind": "frame",
            "think": content.think,
            "operation": content.operation,
            "expect": content.expect,
            "observation": content.observation,
            "verdict": content.verdict,
            "signals": {"::".join(k): v for k, v in content.signals.items()},
        }
    return {"kind": "summary", "schema_version": content.schema_version, "body": content.body}


def _framestream_from_dict(d: dict) -> "FrameStream":
    entries = []
    for e in d.get("entries", []):
        c = e["content"]
        if c["kind"] == "frame":
            content = FrameContent(
                think=c["think"], operation=c["operation"], expect=c["expect"],
                observation=c["observation"], verdict=c["verdict"],
                signals={tuple(k.split("::")): v for k, v in c["signals"].items()},
            )
        else:
            content = SummaryContent(schema_version=c["schema_version"], body=c["body"])
        entries.append(Entry(layer=e["layer"], n_start=e["n_start"], n_end=e["n_end"], content=content))
    return FrameStream(entries=entries)


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
            else Ping(system_prompt="", state=State(frame_stream=FrameStream(entries=[]), signals={}))
        )
        return cls(
            number=d["number"],
            ping=ping,
            pong=Pong.from_dict(d.get("pong", {})),
            observation=Observation.from_dict(d.get("observation", {})),
        )


def flatten_frame_dict(d: dict) -> dict:
    """Translate a FrameRecord.to_dict() shape to the flat wire shape.

    Wire fields mirror SQLite frame_content columns per docs/architecture/kernel/
    04-frame-log.md §4.3. obs_error / verdict_error carry resolved error text.
    signals is always [] until PR 4 SQLite-direct sourcing.
    """
    pong = d.get("pong", {}) or {}
    action = pong.get("action", {}) or {}
    obs = d.get("observation", {}) or {}
    n = d["number"]
    return {
        "n": n,
        "layer": 0,
        "n_start": n,
        "n_end": n,
        "pong_think": pong.get("think", ""),
        "pong_operation": action.get("operation", ""),
        "pong_expect": action.get("expect", ""),
        "obs_stdout": obs.get("stdout", ""),
        "obs_stderr": "",
        "obs_diff_json": obs.get("diff", ""),
        "obs_error": obs.get("error"),
        "verdict_value": obs.get("verdict"),
        "verdict_error": None,
        "signals": [],
    }


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
    "flatten_frame_dict",
    "FrameContent", "SummaryContent", "Entry", "FrameStream",
]
