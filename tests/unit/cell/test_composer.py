"""test_composer.py — Core composer flattens dataclass Ping to LLM messages."""
from __future__ import annotations

from vessal.ark.shell.hull.cell.core.composer import compose
from vessal.ark.shell.hull.cell.protocol import (
    Entry, FrameContent, FrameStream, Ping, State, SummaryContent,
)


def _layer0(n: int, op: str = "x = 1") -> Entry:
    return Entry(
        layer=0, n_start=n, n_end=n,
        content=FrameContent(
            think="", operation=op, expect="True",
            observation={"stdout": "", "stderr": "", "diff": [], "error": None},
            verdict={"total": 1, "passed": 1, "failures": []},
            signals={},
        ),
    )


def test_compose_emits_two_messages_system_and_user():
    ping = Ping(
        system_prompt="You are an agent.",
        state=State(
            frame_stream=FrameStream(entries=[_layer0(1, "a = 1")]),
            signals={("ChatSkill", "chat", "L"): {"unread": 3}},
        ),
    )
    messages = compose(ping)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are an agent."
    assert messages[1]["role"] == "user"
    body = messages[1]["content"]
    assert "frame stream" in body
    assert "frame 1" in body
    assert "a = 1" in body
    assert "ChatSkill" in body
    assert "unread" in body


def test_compose_layer0_frame_block_format():
    ping = Ping(
        system_prompt="",
        state=State(
            frame_stream=FrameStream(entries=[
                Entry(layer=0, n_start=42, n_end=42, content=FrameContent(
                    think="thinking",
                    operation="x = 1",
                    expect="x == 1",
                    observation={"stdout": "ok\n", "stderr": "", "diff": [{"op": "+", "name": "x", "type": "int"}], "error": None},
                    verdict={"total": 1, "passed": 1, "failures": []},
                    signals={},
                )),
            ]),
            signals={},
        ),
    )
    body = compose(ping)[0]["content"]
    assert "── frame 42 ──" in body
    assert "[think]\nthinking" in body
    assert "[operation]\nx = 1" in body
    assert "[expect]\nx == 1" in body
    assert "[stdout]\nok" in body


def test_compose_layer1_summary_block_format():
    ping = Ping(
        system_prompt="",
        state=State(
            frame_stream=FrameStream(entries=[
                Entry(layer=1, n_start=1, n_end=16, content=SummaryContent(
                    schema_version=1, body="summary text",
                )),
            ]),
            signals={},
        ),
    )
    body = compose(ping)[0]["content"]
    assert "── summary [1..16] ──" in body
    assert "summary text" in body


def test_compose_empty_frame_stream_omits_section():
    ping = Ping(
        system_prompt="sys",
        state=State(frame_stream=FrameStream(entries=[]), signals={}),
    )
    messages = compose(ping)
    # Empty user block becomes single system message
    assert len(messages) == 1
    assert messages[0]["role"] == "system"


def test_compose_empty_system_prompt_omits_system_message():
    ping = Ping(
        system_prompt="",
        state=State(frame_stream=FrameStream(entries=[]), signals={}),
    )
    messages = compose(ping)
    assert messages == []


def test_compose_signals_grouped_by_skill():
    ping = Ping(
        system_prompt="",
        state=State(
            frame_stream=FrameStream(entries=[]),
            signals={
                ("ChatSkill", "chat", "L"): {"unread": 3},
                ("ClockSkill", "clock", "G"): {"now": "2026-04-28"},
            },
        ),
    )
    body = compose(ping)[0]["content"]
    assert "ChatSkill" in body and "chat" in body and "unread" in body
    assert "ClockSkill" in body and "clock" in body and "now" in body


class TestComposerDiffList:
    """Composer renders diff list[{op,name,type}] (spec §3.4)."""

    def test_format_diff_renders_list(self):
        from vessal.ark.shell.hull.cell.core.composer import _format_diff
        diff = [
            {"op": "+", "name": "x", "type": "int"},
            {"op": "-", "name": "y", "type": "str"},
        ]
        out = _format_diff(diff)
        assert "+ x: int" in out
        assert "- y: str" in out

    def test_format_diff_empty_list_is_empty_string(self):
        from vessal.ark.shell.hull.cell.core.composer import _format_diff
        assert _format_diff([]) == ""


class TestComposerVerdictShape:
    """Composer renders Verdict.to_dict() = {total, passed, failures} (spec §3.5)."""

    def test_format_verdict_all_passed(self):
        from vessal.ark.shell.hull.cell.core.composer import _format_verdict
        out = _format_verdict({"total": 3, "passed": 3, "failures": []})
        assert "3/3" in out

    def test_format_verdict_with_failures(self):
        from vessal.ark.shell.hull.cell.core.composer import _format_verdict
        out = _format_verdict({
            "total": 2, "passed": 1,
            "failures": [{"kind": "assertion_failed", "assertion": "assert x == 1", "message": "x is 0"}],
        })
        assert "1/2" in out
        assert "assert x == 1" in out
        assert "x is 0" in out
