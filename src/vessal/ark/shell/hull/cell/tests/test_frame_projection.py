# tests/unit/test_frame_projection.py — FrameRecord projection function tests
#
# Coverage:
#   TestProjectFrame     correct rendering and omission logic for each section of project_frame()

import pytest

from vessal.ark.shell.hull.cell.protocol import (
    FRAME_SCHEMA_VERSION,
    Action,
    FrameRecord,
    Observation,
    Ping,
    Pong,
    State,
    Verdict,
    VerdictFailure,
)
from vessal.ark.shell.hull.cell.kernel.render._frame_render import project_frame


# ─────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────


def make_frame(
    number: int = 1,
    task_path: tuple = (),
    think: str = "",
    operation: str = "x = 1",
    expect: str = "",
    stdout: str = "",
    diff: str = "",
    error: str | None = None,
    verdict: Verdict | None = None,
) -> FrameRecord:
    pong = Pong(
        think=think,
        action=Action(operation=operation, expect=expect),
    )
    obs = Observation(stdout=stdout, diff=diff, error=error, verdict=verdict)
    return FrameRecord(
        number=number,
        ping=Ping(system_prompt="", state=State(frame_stream="", signals="")),
        pong=pong,
        observation=obs,
    )


# ─────────────────────────────────────────────
# TestProjectFrame
# ─────────────────────────────────────────────


class TestProjectFrame:
    """project_frame() projection function tests."""

    # ── frame header ──

    def test_header_contains_frame_number(self):
        """Output contains the frame number."""
        frame = make_frame(number=5)
        output = project_frame(frame)
        assert "frame 5" in output

    def test_header_format(self):
        """Frame header format is correct (no frame_type)."""
        frame = make_frame(number=1)
        output = project_frame(frame)
        assert "── frame 1 ──" in output

    # ── think section ──

    def test_think_section_present_when_nonempty(self):
        """When think is non-empty and include_think=True, [think] section appears."""
        frame = make_frame(think="this is the reasoning process")
        output = project_frame(frame, include_think=True)
        assert "[think]" in output
        assert "this is the reasoning process" in output

    def test_think_section_omitted_when_empty(self):
        """When think is empty, [think] section is omitted."""
        frame = make_frame(think="")
        output = project_frame(frame)
        assert "[think]" not in output

    def test_think_section_omitted_when_include_think_false(self):
        """When include_think=False, [think] section is omitted (even if think is non-empty)."""
        frame = make_frame(think="reasoning content")
        output = project_frame(frame, include_think=False)
        assert "[think]" not in output
        assert "reasoning content" not in output

    # ── operation section ──

    def test_operation_always_present(self):
        """[operation] section is always present."""
        frame = make_frame(operation="x = 42")
        output = project_frame(frame)
        assert "[operation]" in output
        assert "x = 42" in output

    # ── expect section ──

    def test_expect_section_present_when_nonempty(self):
        """When expect is non-empty, [expect] section appears."""
        frame = make_frame(expect="assert x == 42")
        output = project_frame(frame)
        assert "[expect]" in output
        assert "assert x == 42" in output

    def test_expect_section_omitted_when_empty(self):
        """When expect is empty, [expect] section is omitted."""
        frame = make_frame(expect="")
        output = project_frame(frame)
        assert "[expect]" not in output

    # ── stdout section ──

    def test_stdout_section_present_when_nonempty(self):
        """When stdout is non-empty, [stdout] section appears."""
        frame = make_frame(stdout="hello world\n")
        output = project_frame(frame)
        assert "[stdout]" in output
        assert "hello world" in output

    def test_stdout_section_omitted_when_empty(self):
        """When stdout is empty, [stdout] section is omitted."""
        frame = make_frame(stdout="")
        output = project_frame(frame)
        assert "[stdout]" not in output

    # ── diff section ──

    def test_diff_section_present_when_nonempty(self):
        """When diff is non-empty, [diff] section appears."""
        frame = make_frame(diff="+x = 42")
        output = project_frame(frame)
        assert "[diff]" in output
        assert "+x = 42" in output

    def test_diff_section_omitted_when_empty(self):
        """When diff is empty, [diff] section is omitted."""
        frame = make_frame(diff="")
        output = project_frame(frame)
        assert "[diff]" not in output

    # ── error section ──

    def test_error_section_present_when_not_none(self):
        """When error is not None, [error] section appears."""
        frame = make_frame(error="ZeroDivisionError: division by zero")
        output = project_frame(frame)
        assert "[error]" in output
        assert "ZeroDivisionError" in output

    def test_error_section_omitted_when_none(self):
        """When error is None, [error] section is omitted."""
        frame = make_frame(error=None)
        output = project_frame(frame)
        assert "[error]" not in output

    # ── verdict section ──

    def test_verdict_section_present_all_pass(self):
        """When all verdict assertions pass, [verdict] section contains pass information."""
        v = Verdict(total=3, passed=3, failures=())
        frame = make_frame(verdict=v)
        output = project_frame(frame)
        assert "[verdict]" in output
        assert "3/3" in output

    def test_verdict_section_present_with_failures(self):
        """When verdict has failures, [verdict] section contains failure details."""
        vf = VerdictFailure(
            kind="assertion_failed",
            assertion="assert x == 1",
            message="x is 0",
        )
        v = Verdict(total=2, passed=1, failures=(vf,))
        frame = make_frame(verdict=v)
        output = project_frame(frame)
        assert "[verdict]" in output
        assert "1/2" in output
        assert "assertion_failed" in output
        assert "x is 0" in output

    def test_verdict_section_omitted_when_none(self):
        """When verdict is None, [verdict] section is omitted."""
        frame = make_frame(verdict=None)
        output = project_frame(frame)
        assert "[verdict]" not in output

    # ── combined tests ──

    def test_minimal_frame_sections(self):
        """Minimal frame (no think, expect, stdout, diff, error, verdict) has only required sections."""
        frame = make_frame(
            think="",
            expect="",
            stdout="",
            diff="",
            error=None,
            verdict=None,
        )
        output = project_frame(frame)
        # must have
        assert "[operation]" in output
        # must not have
        assert "[wake]" not in output
        assert "[task]" not in output
        assert "[think]" not in output
        assert "[expect]" not in output
        assert "[stdout]" not in output
        assert "[diff]" not in output
        assert "[error]" not in output
        assert "[verdict]" not in output

    def test_full_frame_all_sections(self):
        """Full frame with all non-empty fields has all sections present."""
        vf = VerdictFailure(kind="assertion_failed", assertion="assert z", message="z is False")
        v = Verdict(total=1, passed=0, failures=(vf,))
        frame = make_frame(
            think="reasoning",
            expect="assert z",
            stdout="output",
            diff="+z=False",
            error="RuntimeError",
            verdict=v,
        )
        output = project_frame(frame, include_think=True)
        for section in ["[think]", "[operation]",
                         "[expect]", "[stdout]", "[diff]", "[error]", "[verdict]"]:
            assert section in output, f"missing section: {section}"

    def test_output_ends_with_newline(self):
        """Output ends with a newline."""
        frame = make_frame()
        output = project_frame(frame)
        assert output.endswith("\n")

    def test_section_order(self):
        """Section order: wake → think → operation → expect → stdout → diff → error → verdict."""
        vf = VerdictFailure(kind="assertion_failed", assertion="assert x", message="failed")
        v = Verdict(total=1, passed=0, failures=(vf,))
        frame = make_frame(
            think="thinking",
            expect="assert x",
            stdout="out",
            diff="+x=1",
            error="err",
            verdict=v,
        )
        output = project_frame(frame, include_think=True)
        sections = ["[think]", "[operation]",
                    "[expect]", "[stdout]", "[diff]", "[error]", "[verdict]"]
        positions = [output.index(s) for s in sections]
        assert positions == sorted(positions), "section order is incorrect"


# ─────────────────────────────────────────────
# dict-based projection function tests
# ─────────────────────────────────────────────


from vessal.ark.shell.hull.cell.kernel.render._frame_render import project_frame_dict


def _make_frame_dict(**kwargs):
    base = {
        "number": 1,
        "pong": {"think": "", "action": {"operation": "x = 1", "expect": ""}},
        "observation": {"stdout": "", "diff": "+x = 1", "error": None, "verdict": None},
    }
    base.update(kwargs)
    return base


def test_project_frame_dict_basic():
    frame = _make_frame_dict()
    result = project_frame_dict(frame)
    assert "── frame 1 ──" in result
    assert "[operation]" in result
    assert "x = 1" in result


def test_project_frame_dict_with_stdout():
    frame = _make_frame_dict(observation={"stdout": "hello", "diff": "", "error": None, "verdict": None})
    result = project_frame_dict(frame)
    assert "[stdout]" in result
    assert "hello" in result


def test_project_frame_dict_omits_empty_sections():
    frame = _make_frame_dict()
    result = project_frame_dict(frame)
    assert "[stdout]" not in result  # empty stdout omitted
    assert "[think]" not in result   # empty think omitted


def test_project_frame_dict_with_verdict():
    verdict_dict = {"total": 2, "passed": 1, "failures": [
        {"kind": "assertion_failed", "assertion": "assert x == 2", "message": "x is 1"}
    ]}
    obs = {"stdout": "", "diff": "", "error": None, "verdict": verdict_dict}
    frame = _make_frame_dict(observation=obs)
    result = project_frame_dict(frame)
    assert "[verdict]" in result
    assert "1/2" in result
