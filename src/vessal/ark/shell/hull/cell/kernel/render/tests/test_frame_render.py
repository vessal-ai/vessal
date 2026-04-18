"""test_frame_render.py — Frame stream rendering tests using FrameStream."""
from vessal.ark.shell.hull.cell.kernel.render._frame_render import (
    render_frame_stream,
    project_frame_dict,
)
from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream
from vessal.ark.shell.hull.cell.protocol import FRAME_SCHEMA_VERSION


def _make_frame(number: int, operation: str = "x = 1") -> dict:
    """Create a minimal frame dict (schema_version 7) for use with FrameStream.commit_frame()."""
    return {
        "schema_version": FRAME_SCHEMA_VERSION,
        "number": number,
        "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
        "pong": {"think": "", "action": {"operation": operation, "expect": ""}},
        "observation": {"stdout": "", "diff": "", "error": None, "verdict": None},
    }


class TestRenderFrameStreamHardDelete:
    """render_frame_stream drops oldest HOT BUCKETS when over budget."""

    def test_no_deletion_under_budget(self):
        """All frames fit in budget — no frames dropped."""
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(_make_frame(1))
        fs.commit_frame(_make_frame(2))
        ns = {"_frame_stream": fs}
        text, dropped = render_frame_stream(ns, budget_tokens=100000)
        assert dropped == 0

    def test_oldest_frames_dropped_over_budget(self):
        """Over budget — oldest hot buckets dropped, dropped > 0."""
        fs = FrameStream(k=16, n=8)
        for i in range(20):
            fs.commit_frame(_make_frame(i, operation="y = " + "x" * 200))
        ns = {"_frame_stream": fs}
        text, dropped = render_frame_stream(ns, budget_tokens=500)
        assert dropped > 0

    def test_at_least_one_frame_rendered(self):
        """Even with tiny budget, at least 1 frame is rendered."""
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(_make_frame(1))
        fs.commit_frame(_make_frame(2))
        fs.commit_frame(_make_frame(3))
        ns = {"_frame_stream": fs}
        text, dropped = render_frame_stream(ns, budget_tokens=1)
        assert "── frame" in text

    def test_newest_frame_survives(self):
        """The most recent frame is always present in the rendered output."""
        fs = FrameStream(k=16, n=8)
        for i in range(20):
            fs.commit_frame(_make_frame(i, operation="data = " + "x" * 200))
        ns = {"_frame_stream": fs}
        text, dropped = render_frame_stream(ns, budget_tokens=500)
        # frame 19 (newest) must appear
        assert "── frame 19 ──" in text

    def test_empty_frame_stream_no_error(self):
        """Empty FrameStream produces empty output, no frames dropped."""
        ns = {"_frame_stream": FrameStream()}
        text, dropped = render_frame_stream(ns, budget_tokens=100)
        assert text == ""
        assert dropped == 0


def test_render_prefix_stable_on_hot_append():
    """Committing a frame to B_0 must not change any bytes before the first hot byte."""
    fs = FrameStream(k=4, n=2)
    fs.commit_frame({
        "schema_version": 7, "number": 1,
        "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
        "pong": {"think": "t1", "action": {"operation": "op1", "expect": ""}},
        "observation": {"stdout": "", "diff": "", "error": None, "verdict": None},
    })
    text_before, _ = render_frame_stream({"_frame_stream": fs}, budget_tokens=10_000)
    fs.commit_frame({
        "schema_version": 7, "number": 2,
        "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
        "pong": {"think": "t2", "action": {"operation": "op2", "expect": ""}},
        "observation": {"stdout": "", "diff": "", "error": None, "verdict": None},
    })
    text_after, _ = render_frame_stream({"_frame_stream": fs}, budget_tokens=10_000)
    assert text_after.startswith(text_before)
