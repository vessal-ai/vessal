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
    diff: list | None = None,
    error: BaseException | None = None,
) -> Observation:
    return Observation(stdout=stdout, stderr="", diff=diff if diff is not None else [], error=error)


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
        """Observation stores four fields: stdout, stderr, diff, error."""
        obs = Observation(
            stdout="hello\n",
            stderr="",
            diff=[{"op": "+", "name": "x", "type": "int"}],
            error=None,
        )
        assert obs.stdout == "hello\n"
        assert obs.stderr == ""
        assert obs.diff == [{"op": "+", "name": "x", "type": "int"}]
        assert obs.error is None

    def test_with_error_exception(self):
        """error can be a BaseException instance."""
        exc = ZeroDivisionError("division by zero")
        obs = Observation(stdout="", stderr="", diff=[], error=exc)
        assert obs.error is exc

    def test_to_dict_no_verdict_key(self):
        """to_dict does not include a verdict key."""
        obs = Observation(stdout="", stderr="", diff=[], error=None)
        d = obs.to_dict()
        assert "verdict" not in d

    def test_to_dict_roundtrip(self):
        """Roundtrip via to_dict is correct (error loses exception object on deserialise)."""
        original = Observation(stdout="out", stderr="", diff=[{"op": "+", "name": "x", "type": "int"}], error=None)
        d = original.to_dict()
        restored = Observation(
            stdout=d.get("stdout", ""),
            stderr=d.get("stderr", ""),
            diff=list(d.get("diff", [])),
            error=None,
        )
        assert restored == original

    def test_to_dict_error_serialised_as_repr(self):
        """error is serialised via repr() in to_dict."""
        exc = ValueError("bad input")
        obs = Observation(stdout="", stderr="", diff=[], error=exc)
        d = obs.to_dict()
        assert "ValueError" in d["error"]
        assert "bad input" in d["error"]

    def test_to_dict_keys(self):
        """to_dict contains exactly the four expected keys."""
        obs = make_observation()
        assert set(obs.to_dict().keys()) == {"stdout", "stderr", "diff", "error"}


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
        """FrameRecord roundtrip is consistent."""
        obs = Observation(stdout="out\n", stderr="", diff=[{"op": "+", "name": "z", "type": "int"}], error=None)
        original = make_frame_record(observation=obs)
        restored = FrameRecord.from_dict(original.to_dict())
        assert restored == original

    def test_to_dict_roundtrip_minimal(self):
        """Minimal FrameRecord roundtrip is consistent."""
        obs = Observation(stdout="", stderr="", diff=[], error=None)
        original = make_frame_record(observation=obs)
        restored = FrameRecord.from_dict(original.to_dict())
        assert restored == original


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
        assert set(obs.to_dict().keys()) == {"stdout", "stderr", "diff", "error"}

    def test_verdict_keys(self):
        """Verdict.to_dict() key names are stable."""
        v = Verdict(total=0, passed=0, failures=())
        assert set(v.to_dict().keys()) == {"total", "passed", "failures"}

    def test_verdict_failure_keys(self):
        """VerdictFailure.to_dict() key names are stable."""
        vf = make_verdict_failure()
        assert set(vf.to_dict().keys()) == {"kind", "assertion", "message"}
