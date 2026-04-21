from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream

_SCHEMA = 7


def _frame(number: int, diff: str = "", operation: str = "") -> dict:
    return {
        "schema_version": _SCHEMA,
        "number": number,
        "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
        "pong": {"think": "", "action": {"operation": operation, "expect": ""}},
        "observation": {
            "stdout": "",
            "diff": diff,
            "error": "",
            "verdict": {"total": 0, "passed": 0, "failures": []},
        },
    }


def test_latest_hot_frame_returns_most_recent_or_none():
    fs = FrameStream(k=16, n=8)
    assert fs.latest_hot_frame() is None
    fs.commit_frame(_frame(1, diff="+ x", operation="x=1"))
    fs.commit_frame(_frame(2, diff="+ y", operation="y=2"))
    assert fs.latest_hot_frame()["number"] == 2


def test_hot_head_len_counts_b0_bucket():
    fs = FrameStream(k=16, n=8)
    assert fs.hot_head_len() == 0
    fs.commit_frame(_frame(1))
    assert fs.hot_head_len() == 1


def test_find_creation_returns_operation_that_introduced_key():
    fs = FrameStream(k=16, n=8)
    fs.commit_frame(_frame(1, diff="+ foo\n- bar", operation="foo = 42"))
    assert fs.find_creation("foo") == "foo = 42"
    assert fs.find_creation("missing") is None
