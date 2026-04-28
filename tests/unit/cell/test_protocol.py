import pytest
from vessal.ark.shell.hull.cell.protocol import (
    Action, State, Pong, Ping, Observation, StepResult, FrameRecord,
    Verdict, VerdictFailure,
    FRAME_SCHEMA_VERSION,
    FrameStream, Entry, FrameContent,
)

_EMPTY_FS = FrameStream(entries=[])


class TestAction:
    def test_to_dict(self):
        a = Action(operation="x=1", expect="assert x==1")
        assert a.to_dict() == {"operation": "x=1", "expect": "assert x==1"}

    def test_from_dict_roundtrip(self):
        a = Action(operation="pass", expect="")
        a2 = Action.from_dict(a.to_dict())
        assert a2 == a

    def test_from_dict_missing_keys_defaults(self):
        a = Action.from_dict({})
        assert a.operation == ""
        assert a.expect == ""


class TestState:
    def test_fields(self):
        s = State(frame_stream=_EMPTY_FS, signals={("A", "b", "L"): {"x": 1}})
        assert s.frame_stream is _EMPTY_FS
        assert s.signals == {("A", "b", "L"): {"x": 1}}

    def test_immutable(self):
        s = State(frame_stream=_EMPTY_FS, signals={})
        with pytest.raises(Exception):
            s.frame_stream = FrameStream(entries=[])  # frozen

    def test_to_dict(self):
        s = State(frame_stream=_EMPTY_FS, signals={})
        d = s.to_dict()
        assert d == {"frame_stream": {"entries": []}, "signals": {}}

    def test_from_dict_roundtrip(self):
        s = State(frame_stream=_EMPTY_FS, signals={})
        s2 = State.from_dict(s.to_dict())
        assert s2 == s

    def test_from_dict_missing_keys_defaults(self):
        s = State.from_dict({})
        assert s.frame_stream == FrameStream(entries=[])
        assert s.signals == {}


class TestPing:
    def test_two_fields(self):
        p = Ping(system_prompt="sys", state=State(frame_stream=_EMPTY_FS, signals={}))
        assert p.system_prompt == "sys"
        assert p.state.frame_stream == _EMPTY_FS
        assert p.state.signals == {}

    def test_immutable(self):
        p = Ping(system_prompt="a", state=State(frame_stream=_EMPTY_FS, signals={}))
        with pytest.raises(Exception):
            p.system_prompt = "x"  # frozen

    def test_to_dict(self):
        p = Ping(system_prompt="sys", state=State(frame_stream=_EMPTY_FS, signals={}))
        d = p.to_dict()
        assert d == {"system_prompt": "sys", "state": {"frame_stream": {"entries": []}, "signals": {}}}

    def test_from_dict_roundtrip(self):
        p = Ping(system_prompt="sys", state=State(frame_stream=_EMPTY_FS, signals={}))
        p2 = Ping.from_dict(p.to_dict())
        assert p2 == p

    def test_from_dict_missing_keys_defaults(self):
        p = Ping.from_dict({})
        assert p.system_prompt == ""
        assert p.state.frame_stream == FrameStream(entries=[])


class TestPong:
    def test_fields(self):
        pong = Pong(think="t", action=Action(operation="print(1)", expect=""))
        assert pong.think == "t"
        assert pong.action.operation == "print(1)"
        assert pong.action.expect == ""
        assert not hasattr(pong, "raw_response")
        assert not hasattr(pong, "operation")

    def test_to_dict(self):
        pong = Pong(think="t", action=Action(operation="x=1", expect="assert x==1"))
        d = pong.to_dict()
        assert d == {"think": "t", "action": {"operation": "x=1", "expect": "assert x==1"}}

    def test_from_dict_nested(self):
        d = {"think": "reasoning", "action": {"operation": "pass", "expect": ""}}
        pong = Pong.from_dict(d)
        assert pong.think == "reasoning"
        assert pong.action.operation == "pass"
        assert pong.action.expect == ""

    def test_from_dict_old_flat_format(self):
        # backward compat: old format had operation/expect at top level, no "action" key
        d = {"think": "t", "operation": "x=1", "expect": "assert x==1"}
        pong = Pong.from_dict(d)
        assert pong.think == "t"
        assert pong.action.operation == "x=1"
        assert pong.action.expect == "assert x==1"

    def test_from_dict_empty(self):
        pong = Pong.from_dict({})
        assert pong.think == ""
        assert pong.action.operation == ""


class TestStepResult:
    def test_default_none(self):
        result = StepResult()
        assert result.protocol_error is None
        assert not hasattr(result, "frame")

    def test_with_error(self):
        result = StepResult(protocol_error="parse failed")
        assert result.protocol_error == "parse failed"

    def test_no_frame_field(self):
        result = StepResult(protocol_error=None)
        assert not hasattr(result, "frame")


class TestFrameRecord:
    def test_schema_version_is_7(self):
        assert FRAME_SCHEMA_VERSION == 7

    def _make_record(self, number: int = 1) -> FrameRecord:
        ping = Ping(system_prompt="sys", state=State(frame_stream=_EMPTY_FS, signals={}))
        pong = Pong(think="", action=Action(operation="pass", expect=""))
        obs = Observation(stdout="", diff="", error=None, verdict=None)
        return FrameRecord(number=number, ping=ping, pong=pong, observation=obs)

    def test_fields(self):
        fr = self._make_record()
        assert fr.number == 1
        assert fr.ping.system_prompt == "sys"
        assert not hasattr(fr, "frame_type")
        assert not hasattr(fr, "wake_reason")
        assert not hasattr(fr, "raw_response")
        assert not hasattr(fr, "token_usage")
        assert not hasattr(fr, "model")
        assert not hasattr(fr, "timestamp")

    def test_to_dict(self):
        pong = Pong(think="t", action=Action(operation="x=1", expect=""))
        obs = Observation(stdout="out", diff="+x = 1", error=None, verdict=None)
        ping = Ping(system_prompt="sys", state=State(frame_stream=_EMPTY_FS, signals={}))
        fr = FrameRecord(number=3, ping=ping, pong=pong, observation=obs)
        d = fr.to_dict()
        assert d["schema_version"] == 7
        assert d["number"] == 3
        assert d["ping"]["system_prompt"] == "sys"
        assert d["ping"]["state"]["signals"] == {}
        assert d["pong"]["action"]["operation"] == "x=1"
        assert d["observation"]["stdout"] == "out"
        assert "frame_type" not in d
        assert "wake_reason" not in d
        assert "raw_response" not in d
        assert "token_usage" not in d
        assert "model" not in d
        assert "timestamp" not in d

    def test_from_dict_roundtrip(self):
        fr = self._make_record(number=3)
        d = fr.to_dict()
        fr2 = FrameRecord.from_dict(d)
        assert fr2.number == fr.number
        assert fr2.ping.system_prompt == fr.ping.system_prompt
        assert fr2.ping.state.signals == fr.ping.state.signals
        assert fr2.pong.action.operation == fr.pong.action.operation

    def test_from_dict_v5_compat(self):
        """v5 format (no ping field) can still be deserialized, ping is populated with an empty Ping."""
        v5 = {
            "schema_version": 5, "number": 1,
            "pong": {"think": "", "action": {"operation": "x=1", "expect": ""}},
            "observation": {"stdout": "", "diff": "", "error": None, "verdict": None},
        }
        fr = FrameRecord.from_dict(v5)
        assert fr.number == 1
        assert fr.ping.system_prompt == ""
        assert fr.ping.state.frame_stream == FrameStream(entries=[])

    def test_from_dict_no_version_check(self):
        # from_dict should NOT raise on version mismatch — migration is handled elsewhere
        fr = self._make_record()
        d = fr.to_dict()
        d["schema_version"] = 1  # old version — should not raise
        fr2 = FrameRecord.from_dict(d)
        assert fr2.number == 1

    def test_from_dict_missing_version_does_not_raise(self):
        fr = self._make_record()
        d = fr.to_dict()
        del d["schema_version"]
        fr2 = FrameRecord.from_dict(d)
        assert fr2.number == 1

    def test_frame_record_v6_includes_ping(self):
        ping = Ping(system_prompt="sys", state=State(frame_stream=_EMPTY_FS, signals={}))
        pong = Pong(think="t", action=Action(operation="x=1", expect=""))
        obs = Observation(stdout="", diff="+ x: 1", error=None, verdict=None)
        record = FrameRecord(number=1, ping=ping, pong=pong, observation=obs)
        d = record.to_dict()
        assert d["schema_version"] == 7
        assert d["ping"]["system_prompt"] == "sys"
        assert d["ping"]["state"]["signals"] == {}



class TestFromDictRoundtrips:
    def test_observation_from_dict(self):
        obs = Observation(stdout="hello", diff="+x=1", error="oops", verdict=None)
        assert Observation.from_dict(obs.to_dict()) == obs

    def test_verdict_from_dict(self):
        vf = VerdictFailure(kind="assertion_failed", assertion="assert x == 1", message="x is 2")
        v = Verdict(total=2, passed=1, failures=(vf,))
        v2 = Verdict.from_dict(v.to_dict())
        assert v2.total == 2
        assert v2.passed == 1
        assert len(v2.failures) == 1
        assert v2.failures[0].assertion == "assert x == 1"
