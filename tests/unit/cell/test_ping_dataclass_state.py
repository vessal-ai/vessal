"""test_ping_dataclass_state.py — State.frame_stream is FrameStream dataclass, signals is dict."""
from vessal.ark.shell.hull.cell.protocol import (
    Entry, FrameContent, FrameStream, Ping, State,
)


def test_state_frame_stream_is_framestream_dataclass():
    fs = FrameStream(entries=[])
    state = State(frame_stream=fs, signals={})
    assert state.frame_stream is fs
    assert isinstance(state.frame_stream, FrameStream)


def test_state_signals_is_dict():
    state = State(frame_stream=FrameStream(entries=[]), signals={("A", "b", "L"): {"x": 1}})
    assert state.signals == {("A", "b", "L"): {"x": 1}}


def test_state_to_dict_includes_entries_count():
    """to_dict() must serialize FrameStream — at minimum entries length."""
    state = State(
        frame_stream=FrameStream(entries=[
            Entry(layer=0, n_start=1, n_end=1, content=FrameContent(
                think="", operation="x=1", expect="True",
                observation={"stdout": "", "stderr": "", "diff": {}, "error": None},
                verdict=None, signals={},
            )),
        ]),
        signals={},
    )
    d = state.to_dict()
    assert "frame_stream" in d
    assert isinstance(d["frame_stream"], dict)
    assert d["frame_stream"]["entries"] and len(d["frame_stream"]["entries"]) == 1


def test_string_state_construction_rejected():
    """Old call sites passing strings must fail loudly."""
    import pytest
    fs = FrameStream(entries=[])
    state = State(frame_stream=fs, signals={})
    assert not isinstance(state.frame_stream, str)
    assert not isinstance(state.signals, str)
