"""test_frame_render.py — Frame stream rendering + hard frame deletion tests."""
from vessal.ark.shell.hull.cell.kernel.render._frame_render import (
    render_frame_stream,
    project_frame_dict,
)


def _make_frame(number: int, operation: str = "x = 1") -> dict:
    """Create a minimal frame dict for testing."""
    return {
        "number": number,
        "pong": {"think": "", "action": {"operation": operation, "expect": ""}},
        "observation": {"stdout": "", "diff": "", "error": None, "verdict": None},
    }


class TestRenderFrameStreamHardDelete:
    """render_frame_stream physically deletes oldest frames when over budget."""

    def test_no_deletion_under_budget(self):
        """All frames fit in budget — no deletion."""
        ns = {"_frame_log": [_make_frame(1), _make_frame(2)]}
        text, dropped = render_frame_stream(ns, budget_tokens=100000)
        assert dropped == 0
        assert len(ns["_frame_log"]) == 2

    def test_oldest_frames_deleted_over_budget(self):
        """Over budget — oldest frames physically removed from _frame_log."""
        frames = [_make_frame(i, operation="y = " + "x" * 200) for i in range(20)]
        ns = {"_frame_log": frames}
        original_count = len(ns["_frame_log"])
        text, dropped = render_frame_stream(ns, budget_tokens=500)
        # Frames should be physically deleted
        assert len(ns["_frame_log"]) < original_count
        assert dropped > 0
        # At least 1 frame survives
        assert len(ns["_frame_log"]) >= 1

    def test_at_least_one_frame_survives(self):
        """Even with tiny budget, at least 1 frame remains."""
        ns = {"_frame_log": [_make_frame(1), _make_frame(2), _make_frame(3)]}
        text, dropped = render_frame_stream(ns, budget_tokens=1)
        assert len(ns["_frame_log"]) >= 1

    def test_deleted_frames_are_oldest(self):
        """Deletion removes the oldest frames, keeping newest."""
        frames = [_make_frame(i, operation="data = " + "x" * 200) for i in range(10)]
        ns = {"_frame_log": frames}
        render_frame_stream(ns, budget_tokens=500)
        # Remaining frames should be the newest ones (highest numbers)
        remaining_numbers = [f["number"] for f in ns["_frame_log"]]
        assert remaining_numbers == sorted(remaining_numbers)
        assert remaining_numbers[-1] == 9  # newest frame survives

    def test_empty_frame_log_no_error(self):
        """Empty frame log produces empty output, no deletion."""
        ns = {"_frame_log": []}
        text, dropped = render_frame_stream(ns, budget_tokens=100)
        assert text == ""
        assert dropped == 0
