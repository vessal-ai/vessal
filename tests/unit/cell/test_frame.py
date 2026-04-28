# tests/unit/test_frame.py — v5 Canonical Frame Protocol data structure tests
#
# Coverage:
#   TestVerdictFailure     field completeness, to_dict/from_dict roundtrip
#   TestVerdict            field completeness, to_dict/from_dict roundtrip
#   TestAction             field completeness, to_dict/from_dict roundtrip
#   TestPong               field completeness, to_dict/from_dict roundtrip
#   TestObservation        field completeness, to_dict/from_dict roundtrip (including verdict=None)
#   TestTaskPathEntry      field completeness, to_dict/from_dict roundtrip
#   TestFrameRecord        field completeness, to_dict/from_dict roundtrip, schema_version guard
#   TestImmutability       all dataclass frozen verification
#   TestJsonKeyStability   FrameRecord serialization key name stability

import pytest

from vessal.ark.shell.hull.cell.protocol import (
    Action,
    FrameRecord,
    FrameStream,
    Observation,
    Ping,
    Pong,
    State,
    Verdict,
    VerdictFailure,
)


# ─────────────────────────────────────────────
# Test helper fixtures
# ─────────────────────────────────────────────


def make_verdict_failure(
    kind: str = "assertion_failed",
    assertion: str = "assert x == 1",
    message: str = "x is not equal to 1",
) -> VerdictFailure:
    return VerdictFailure(kind=kind, assertion=assertion, message=message)  # type: ignore[arg-type]


def make_verdict(
    total: int = 2,
    passed: int = 1,
    failures: tuple = (),
) -> Verdict:
    if not failures:
        failures = (make_verdict_failure(),)
    return Verdict(total=total, passed=passed, failures=failures)


def make_action(
    operation: str = "x = 1",
    expect: str = "assert x == 1",
) -> Action:
    return Action(operation=operation, expect=expect)


def make_pong(
    think: str = "reasoning process",
    operation: str = "x = 1",
    expect: str = "assert x == 1",
) -> Pong:
    return Pong(
        think=think,
        action=Action(operation=operation, expect=expect),
    )


def make_observation(
    stdout: str = "hello\n",
    diff: str = "+x = 1",
    error: str | None = None,
    verdict: Verdict | None = None,
) -> Observation:
    return Observation(stdout=stdout, diff=diff, error=error, verdict=verdict)


def make_frame_record(**overrides) -> FrameRecord:
    """Construct a minimal valid FrameRecord, supporting field overrides."""
    defaults: dict = {
        "number": 1,
        "ping": Ping(system_prompt="", state=State(frame_stream=FrameStream(entries=[]), signals={})),
        "pong": make_pong(),
        "observation": make_observation(),
    }
    defaults.update(overrides)
    return FrameRecord(**defaults)


# ─────────────────────────────────────────────
# TestVerdictFailure
# ─────────────────────────────────────────────


class TestVerdictFailure:
    """VerdictFailure data structure tests."""

    def test_fields_complete(self):
        """VerdictFailure stores three fields: kind, assertion, message."""
        vf = VerdictFailure(
            kind="assertion_failed",
            assertion="assert x == 1",
            message="x is not equal to 1",
        )
        assert vf.kind == "assertion_failed"
        assert vf.assertion == "assert x == 1"
        assert vf.message == "x is not equal to 1"

    def test_all_kinds_valid(self):
        """All four kind values can create a VerdictFailure."""
        kinds = [
            "assertion_failed",
            "expect_syntax_error",
            "expect_unsafe_error",
            "expect_runtime_error",
        ]
        for kind in kinds:
            vf = VerdictFailure(kind=kind, assertion="assert True", message="ok")  # type: ignore[arg-type]
            assert vf.kind == kind

    def test_to_dict_roundtrip(self):
        """to_dict → from_dict roundtrip is consistent."""
        original = VerdictFailure(
            kind="expect_runtime_error",
            assertion="assert len(x) > 0",
            message="TypeError: object of type 'int' has no len()",
        )
        restored = VerdictFailure.from_dict(original.to_dict())
        assert restored == original

    def test_to_dict_keys(self):
        """to_dict contains exactly: kind, assertion, message."""
        vf = make_verdict_failure()
        d = vf.to_dict()
        assert set(d.keys()) == {"kind", "assertion", "message"}


# ─────────────────────────────────────────────
# TestVerdict
# ─────────────────────────────────────────────


class TestVerdict:
    """Verdict data structure tests."""

    def test_fields_complete(self):
        """Verdict stores three fields: total, passed, failures."""
        vf = make_verdict_failure()
        v = Verdict(total=3, passed=2, failures=(vf,))
        assert v.total == 3
        assert v.passed == 2
        assert len(v.failures) == 1

    def test_empty_failures(self):
        """failures can be an empty tuple."""
        v = Verdict(total=1, passed=1, failures=())
        assert v.failures == ()

    def test_to_dict_roundtrip(self):
        """to_dict → from_dict roundtrip is consistent."""
        vf = make_verdict_failure()
        original = Verdict(total=2, passed=1, failures=(vf,))
        restored = Verdict.from_dict(original.to_dict())
        assert restored == original

    def test_to_dict_keys(self):
        """to_dict contains exactly: total, passed, failures."""
        v = Verdict(total=0, passed=0, failures=())
        assert set(v.to_dict().keys()) == {"total", "passed", "failures"}


# ─────────────────────────────────────────────
# TestAction
# ─────────────────────────────────────────────


class TestAction:
    """Action data structure tests."""

    def test_fields_complete(self):
        """Action stores two fields: operation, expect."""
        a = Action(operation="x = 1", expect="assert x == 1")
        assert a.operation == "x = 1"
        assert a.expect == "assert x == 1"

    def test_empty_expect(self):
        """expect can be an empty string."""
        a = Action(operation="pass", expect="")
        assert a.expect == ""

    def test_to_dict_roundtrip(self):
        """to_dict → from_dict roundtrip is consistent."""
        original = make_action()
        restored = Action.from_dict(original.to_dict())
        assert restored == original

    def test_to_dict_keys(self):
        """to_dict contains exactly: operation, expect."""
        a = make_action()
        assert set(a.to_dict().keys()) == {"operation", "expect"}


# ─────────────────────────────────────────────
# TestPong
# ─────────────────────────────────────────────


class TestPong:
    """Pong data structure tests."""

    def test_fields_complete(self):
        """Pong stores two fields: think, action."""
        p = Pong(
            think="thinking",
            action=Action(operation="x=1", expect="assert x == 1"),
        )
        assert p.think == "thinking"
        assert p.action.operation == "x=1"
        assert p.action.expect == "assert x == 1"

    def test_empty_think(self):
        """think can be an empty string."""
        p = Pong(think="", action=Action(operation="pass", expect=""))
        assert p.think == ""

    def test_to_dict_roundtrip(self):
        """to_dict → from_dict roundtrip is consistent."""
        original = make_pong()
        restored = Pong.from_dict(original.to_dict())
        assert restored == original

    def test_to_dict_keys(self):
        """to_dict contains exactly the two expected keys."""
        p = make_pong()
        assert set(p.to_dict().keys()) == {"think", "action"}

    def test_from_dict_compat_flat_format(self):
        """from_dict is compatible with old flat pong dict format (no action key)."""
        flat = {"think": "t", "operation": "x = 1", "expect": "assert x == 1"}
        p = Pong.from_dict(flat)
        assert p.action.operation == "x = 1"
        assert p.action.expect == "assert x == 1"


# ─────────────────────────────────────────────
# TestObservation
# ─────────────────────────────────────────────


class TestObservation:
    """Observation data structure tests."""

    def test_fields_complete(self):
        """Observation stores four fields: stdout, diff, error, verdict."""
        obs = Observation(
            stdout="hello\n",
            diff="+x = 1",
            error=None,
            verdict=None,
        )
        assert obs.stdout == "hello\n"
        assert obs.diff == "+x = 1"
        assert obs.error is None
        assert obs.verdict is None

    def test_with_error_string(self):
        """error can be a string."""
        obs = Observation(stdout="", diff="", error="Traceback: ZeroDivisionError", verdict=None)
        assert obs.error == "Traceback: ZeroDivisionError"

    def test_with_verdict(self):
        """verdict can be a Verdict instance."""
        v = Verdict(total=1, passed=1, failures=())
        obs = Observation(stdout="", diff="", error=None, verdict=v)
        assert obs.verdict is v

    def test_to_dict_verdict_none(self):
        """When verdict=None, to_dict has verdict as None."""
        obs = Observation(stdout="", diff="", error=None, verdict=None)
        d = obs.to_dict()
        assert d["verdict"] is None

    def test_to_dict_roundtrip_no_verdict(self):
        """Roundtrip is correct when verdict=None."""
        original = Observation(stdout="out", diff="+x=1", error=None, verdict=None)
        restored = Observation.from_dict(original.to_dict())
        assert restored == original

    def test_to_dict_roundtrip_with_verdict(self):
        """Roundtrip is correct when verdict is not None."""
        vf = make_verdict_failure()
        v = Verdict(total=2, passed=1, failures=(vf,))
        original = Observation(stdout="", diff="", error="err", verdict=v)
        restored = Observation.from_dict(original.to_dict())
        assert restored == original

    def test_to_dict_keys(self):
        """to_dict contains exactly the four expected keys."""
        obs = make_observation()
        assert set(obs.to_dict().keys()) == {"stdout", "diff", "error", "verdict"}


# ─────────────────────────────────────────────
# TestFrameRecord
# ─────────────────────────────────────────────


class TestFrameRecord:
    """FrameRecord data structure tests."""

    def test_fields_complete(self):
        """FrameRecord contains 4 fields (v6 adds ping)."""
        f = make_frame_record()
        assert f.number == 1
        assert isinstance(f.ping, Ping)
        assert isinstance(f.pong, Pong)
        assert isinstance(f.observation, Observation)
        assert not hasattr(f, "frame_type")
        assert not hasattr(f, "wake_reason")

    def test_to_dict_roundtrip_full(self):
        """Full FrameRecord (with verdict) roundtrip is consistent."""
        vf = VerdictFailure(
            kind="assertion_failed",
            assertion="assert z == 0",
            message="z is 1",
        )
        verdict = Verdict(total=1, passed=0, failures=(vf,))
        obs = Observation(stdout="out\n", diff="+z=1", error=None, verdict=verdict)
        original = make_frame_record(observation=obs)
        restored = FrameRecord.from_dict(original.to_dict())
        assert restored == original

    def test_to_dict_roundtrip_minimal(self):
        """Minimal FrameRecord (no verdict) roundtrip is consistent."""
        obs = Observation(stdout="", diff="", error=None, verdict=None)
        original = make_frame_record(observation=obs)
        restored = FrameRecord.from_dict(original.to_dict())
        assert restored == original

    def test_failures_is_tuple_after_roundtrip(self):
        """After roundtrip, Verdict.failures is still a tuple, not a list."""
        vf = make_verdict_failure()
        v = Verdict(total=1, passed=0, failures=(vf,))
        obs = make_observation(verdict=v)
        original = make_frame_record(observation=obs)
        restored = FrameRecord.from_dict(original.to_dict())
        assert isinstance(restored.observation.verdict.failures, tuple)


# ─────────────────────────────────────────────
# TestImmutability
# ─────────────────────────────────────────────


class TestImmutability:
    """All dataclasses are frozen — assignment should raise an exception."""

    def test_verdict_failure_frozen(self):
        vf = make_verdict_failure()
        with pytest.raises((AttributeError, TypeError)):
            vf.kind = "assertion_failed"  # type: ignore[misc]

    def test_verdict_frozen(self):
        v = Verdict(total=1, passed=1, failures=())
        with pytest.raises((AttributeError, TypeError)):
            v.total = 0  # type: ignore[misc]

    def test_action_frozen(self):
        a = make_action()
        with pytest.raises((AttributeError, TypeError)):
            a.operation = "new code"  # type: ignore[misc]

    def test_pong_frozen(self):
        p = make_pong()
        with pytest.raises((AttributeError, TypeError)):
            p.think = "changed"  # type: ignore[misc]

    def test_observation_frozen(self):
        obs = make_observation()
        with pytest.raises((AttributeError, TypeError)):
            obs.stdout = "changed"  # type: ignore[misc]

    def test_frame_record_frozen(self):
        f = make_frame_record()
        with pytest.raises((AttributeError, TypeError)):
            f.number = 999  # type: ignore[misc]


# ─────────────────────────────────────────────
# TestJsonKeyStability
# ─────────────────────────────────────────────


class TestJsonKeyStability:
    """FrameRecord serialization key name stability tests.

    If these key names change, JSONL logs will be incompatible,
    and FRAME_SCHEMA_VERSION must be bumped in sync.
    """

    def test_frame_record_top_level_keys(self):
        """FrameRecord.to_dict() contains exactly the expected top-level keys."""
        f = make_frame_record()
        d = f.to_dict()
        expected_keys = {
            "schema_version",
            "number",
            "ping",
            "pong",
            "observation",
        }
        assert set(d.keys()) == expected_keys

    def test_pong_keys(self):
        """Pong.to_dict() key names are stable."""
        p = make_pong()
        assert set(p.to_dict().keys()) == {"think", "action"}

    def test_action_keys(self):
        """Action.to_dict() key names are stable."""
        a = make_action()
        assert set(a.to_dict().keys()) == {"operation", "expect"}

    def test_observation_keys(self):
        """Observation.to_dict() key names are stable."""
        obs = make_observation()
        assert set(obs.to_dict().keys()) == {"stdout", "diff", "error", "verdict"}

    def test_verdict_keys(self):
        """Verdict.to_dict() key names are stable."""
        v = Verdict(total=0, passed=0, failures=())
        assert set(v.to_dict().keys()) == {"total", "passed", "failures"}

    def test_verdict_failure_keys(self):
        """VerdictFailure.to_dict() key names are stable."""
        vf = make_verdict_failure()
        assert set(vf.to_dict().keys()) == {"kind", "assertion", "message"}
