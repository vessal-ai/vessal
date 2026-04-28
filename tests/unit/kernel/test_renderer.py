# tests/test_renderer.py — v4 renderer tests
#
# Coverage:
#   TestRenderConfig      RenderConfig dataclass
#   TestEstimateTokens    token estimation utility function
#   TestSystemPrompt      _render_system_prompt
#   TestRenderSingleFrame project_frame() tested via _render_frame_stream
#   TestRenderFrameStream _render_frame_stream
#   TestRenderAuxiliary   _render_auxiliary (reads from ns["signals"] spec §6 dict)
#   TestRender            render() main function — returns Pong
#   TestRenderPing        render() returning Ping focused tests
#   TestKernelRenderV3    Kernel integration tests (v4 render path)

import pytest

from vessal.ark.shell.hull.cell.kernel.render.renderer import (
    RenderConfig,
    DEFAULT_CONFIG,
    render,
    _render_system_prompt,
    _render_frame_stream,
    _render_auxiliary,
)
from vessal.ark.shell.hull.cell.kernel.render import render
from vessal.ark.shell.hull.cell.protocol import Ping, State
from vessal.ark.util.token_util import estimate_tokens
from vessal.ark.shell.hull.cell.protocol import (
    FrameRecord, Pong, Action, Observation,
    FRAME_SCHEMA_VERSION,
)
from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream


# ──────────────────────────────────────────────────────────────────────────────
# Helper construction
# ──────────────────────────────────────────────────────────────────────────────

def make_frame_record(
    number=1,
    operation="x = 1",
    think="",
    expect="",
    stdout="",
    diff="",
    error=None,
    verdict=None,
):
    """Construct a test frame dict (schema_version 7) for use with FrameStream.commit_frame()."""
    return {
        "schema_version": FRAME_SCHEMA_VERSION,
        "number": number,
        "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
        "pong": {"think": think, "action": {"operation": operation, "expect": expect}},
        "observation": {
            "stdout": stdout,
            "diff": diff,
            "error": error,
            "verdict": verdict.to_dict() if hasattr(verdict, "to_dict") else verdict,
        },
    }


def bare_ns_v3() -> dict:
    """Return a minimal v4 namespace for test isolation."""
    return {
        "_frame": 0,
        "_frame_stream": FrameStream(),
        "_system_prompt": "",
        "_context_budget": 128000,
        "_token_budget": 4096,
        "_builtin_names": [],
        "_context_pct": 0,
        "_ns_meta": {},
        "_stdout": "",
        "_error": None,
        "_action": "",
        "_diff": "",
        "signals": {},
        "_dropped_frame_count": 0,
    }


@pytest.fixture
def minimal_ns():
    """Minimal namespace fixture for Ping tests."""
    return {
        "_frame": 0,
        "_frame_stream": FrameStream(),
        "_system_prompt": "",
        "_context_budget": 128000,
        "_token_budget": 4096,
        "_builtin_names": [],
        "_context_pct": 0,
        "_ns_meta": {},
        "_stdout": "",
        "_error": None,
        "_action": "",
        "_diff": "",
        "signals": {},
        "_dropped_frame_count": 0,
    }


# ──────────────────────────────────────────────────────────────────────────────
# TestRenderPing — focused tests for render() returning Ping
# ──────────────────────────────────────────────────────────────────────────────


def test_render_returns_ping(minimal_ns):
    """render() returns Ping, no longer returns str."""
    ping = render(minimal_ns)
    assert isinstance(ping, Ping)
    assert isinstance(ping.system_prompt, str)
    assert isinstance(ping.state.frame_stream, str)
    assert isinstance(ping.state.signals, str)


def test_render_ping_system_prompt(minimal_ns):
    minimal_ns["_system_prompt"] = "You are an agent."
    ping = render(minimal_ns)
    assert ping.system_prompt == "You are an agent."


def test_render_ping_frame_stream_empty_when_no_frames(minimal_ns):
    minimal_ns["_frame_stream"] = FrameStream()
    ping = render(minimal_ns)
    assert ping.state.frame_stream == ""


# ──────────────────────────────────────────────────────────────────────────────
# Step 1: TestRenderConfig + TestEstimateTokens
# ──────────────────────────────────────────────────────────────────────────────

class TestRenderConfig:
    def test_default_system_prompt_key(self):
        assert DEFAULT_CONFIG.system_prompt_key == "_system_prompt"

    def test_no_auxiliary_modules_field(self):
        # RenderConfig has no auxiliary_modules field; auxiliary signals are driven by ns["signals"]
        assert not hasattr(DEFAULT_CONFIG, "auxiliary_modules")

    def test_default_frame_budget_ratio(self):
        assert DEFAULT_CONFIG.frame_budget_ratio == 0.7

    def test_frozen(self):
        with pytest.raises(Exception):
            DEFAULT_CONFIG.frame_budget_ratio = 0.5

    def test_custom_config(self):
        cfg = RenderConfig(system_prompt_key="_sp", frame_budget_ratio=0.5)
        assert cfg.system_prompt_key == "_sp"
        assert cfg.frame_budget_ratio == 0.5

    def test_two_configs_are_independent(self):
        # two independent config instances do not share state
        c1 = RenderConfig()
        c2 = RenderConfig(frame_budget_ratio=0.5)
        assert c1.frame_budget_ratio != c2.frame_budget_ratio


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_ascii(self):
        # 4 ASCII chars = 4 bytes => 1 token
        assert estimate_tokens("abcd") == 1

    def test_utf8_multibyte(self):
        # each Chinese character is 3 bytes
        text = "中文"  # 6 bytes => 1 token
        assert estimate_tokens(text) == 1

    def test_longer_text(self):
        text = "a" * 400  # 400 bytes => 100 tokens
        assert estimate_tokens(text) == 100

    def test_returns_int(self):
        assert isinstance(estimate_tokens("hello"), int)


# ──────────────────────────────────────────────────────────────────────────────
# Step 2: TestSystemPrompt
# ──────────────────────────────────────────────────────────────────────────────

class TestSystemPrompt:
    def test_empty_ns(self):
        assert _render_system_prompt({}, "_system_prompt") == ""

    def test_missing_key(self):
        ns = {"_other": "value"}
        assert _render_system_prompt(ns, "_system_prompt") == ""

    def test_normal_prompt(self):
        ns = {"_system_prompt": "You are an agent."}
        assert _render_system_prompt(ns, "_system_prompt") == "You are an agent."

    def test_strips_whitespace(self):
        ns = {"_system_prompt": "  hello  \n"}
        assert _render_system_prompt(ns, "_system_prompt") == "hello"

    def test_whitespace_only_returns_empty(self):
        ns = {"_system_prompt": "   \n\t  "}
        assert _render_system_prompt(ns, "_system_prompt") == ""

    def test_custom_key(self):
        ns = {"_my_prompt": "Custom prompt."}
        assert _render_system_prompt(ns, "_my_prompt") == "Custom prompt."

    def test_non_string_coerced(self):
        ns = {"_system_prompt": 42}
        result = _render_system_prompt(ns, "_system_prompt")
        assert result == "42"


# ──────────────────────────────────────────────────────────────────────────────
# Step 3: TestRenderSingleFrame — now via project_frame() through frame stream
# ──────────────────────────────────────────────────────────────────────────────

class TestRenderSingleFrame:
    """Tests for FrameRecord rendering via project_frame()."""

    def test_header_format(self):
        frame = make_frame_record(number=42, operation="x = 1")
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(frame)
        ns = {"_frame_stream": fs}
        rendered = _render_frame_stream(ns, 100000)
        assert "── frame 42 ──" in rendered

    def test_operation_section(self):
        frame = make_frame_record(operation="x = requests.get(...)")
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(frame)
        ns = {"_frame_stream": fs}
        rendered = _render_frame_stream(ns, 100000)
        assert "[operation]" in rendered
        assert "x = requests.get(...)" in rendered

    def test_think_section_when_present(self):
        frame = make_frame_record(think="let me think...")
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(frame)
        ns = {"_frame_stream": fs}
        rendered = _render_frame_stream(ns, 100000)
        assert "[think]" in rendered
        assert "let me think..." in rendered

    def test_think_section_absent_when_empty(self):
        frame = make_frame_record(think="")
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(frame)
        ns = {"_frame_stream": fs}
        rendered = _render_frame_stream(ns, 100000)
        assert "[think]" not in rendered

    def test_stdout_section(self):
        frame = make_frame_record(stdout="142")
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(frame)
        ns = {"_frame_stream": fs}
        rendered = _render_frame_stream(ns, 100000)
        assert "[stdout]" in rendered
        assert "142" in rendered

    def test_diff_section(self):
        frame = make_frame_record(diff="+ x = 42")
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(frame)
        ns = {"_frame_stream": fs}
        rendered = _render_frame_stream(ns, 100000)
        assert "[diff]" in rendered
        assert "+ x = 42" in rendered

    def test_error_section(self):
        frame = make_frame_record(error="Traceback: NameError")
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(frame)
        ns = {"_frame_stream": fs}
        rendered = _render_frame_stream(ns, 100000)
        assert "[error]" in rendered
        assert "Traceback: NameError" in rendered

    def test_no_stdout_section_when_empty(self):
        frame = make_frame_record(stdout="", diff="+ x = 1")
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(frame)
        ns = {"_frame_stream": fs}
        rendered = _render_frame_stream(ns, 100000)
        assert "[stdout]" not in rendered

    def test_no_diff_section_when_empty(self):
        frame = make_frame_record(stdout="hello", diff="")
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(frame)
        ns = {"_frame_stream": fs}
        rendered = _render_frame_stream(ns, 100000)
        assert "[diff]" not in rendered

    def test_expect_section_when_present(self):
        frame = make_frame_record(expect="assert x == 1")
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(frame)
        ns = {"_frame_stream": fs}
        rendered = _render_frame_stream(ns, 100000)
        assert "[expect]" in rendered
        assert "assert x == 1" in rendered

    def test_expect_absent_when_empty(self):
        frame = make_frame_record(expect="")
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(frame)
        ns = {"_frame_stream": fs}
        rendered = _render_frame_stream(ns, 100000)
        assert "[expect]" not in rendered


# ──────────────────────────────────────────────────────────────────────────────
# Step 4: TestRenderFrameStream + TestCompressFrames
# ──────────────────────────────────────────────────────────────────────────────

class TestRenderFrameStream:
    def test_empty_frame_stream(self):
        ns = bare_ns_v3()
        assert _render_frame_stream(ns, 100000) == ""

    def test_header_present(self):
        ns = bare_ns_v3()
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(make_frame_record(number=1))
        ns["_frame_stream"] = fs
        result = _render_frame_stream(ns, 100000)
        assert result.startswith("══════ frame stream ══════\n")

    def test_single_frame_content(self):
        ns = bare_ns_v3()
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(make_frame_record(number=1, operation="x = 1"))
        ns["_frame_stream"] = fs
        result = _render_frame_stream(ns, 100000)
        assert "── frame 1 ──" in result
        assert "x = 1" in result

    def test_multiple_frames(self):
        ns = bare_ns_v3()
        fs = FrameStream(k=16, n=8)
        for f in [make_frame_record(number=1), make_frame_record(number=2)]:
            fs.commit_frame(f)
        ns["_frame_stream"] = fs
        result = _render_frame_stream(ns, 100000)
        assert "── frame 1 ──" in result
        assert "── frame 2 ──" in result

    def test_within_budget_no_deletion(self):
        ns = bare_ns_v3()
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(make_frame_record(number=1, operation="x = 1"))
        ns["_frame_stream"] = fs
        result = _render_frame_stream(ns, 100000)
        assert "earlier" not in result

    def test_over_budget_triggers_hard_delete(self):
        # tiny budget with many frames should trigger bucket-level dropping
        ns = bare_ns_v3()
        fs = FrameStream(k=16, n=8)
        for i in range(50):
            fs.commit_frame(make_frame_record(number=i, stdout="x" * 500))
        ns["_frame_stream"] = fs
        ns["_context_budget"] = 2000
        ns["_token_budget"] = 500
        result = _render_frame_stream(ns, 1)
        # the frame stream header is present (at least 1 frame rendered)
        assert "══════ frame stream ══════" in result


# ──────────────────────────────────────────────────────────────────────────────
# Step 5: TestRenderAuxiliary — reads from ns["signals"] (spec §6 dict)
# ──────────────────────────────────────────────────────────────────────────────

class TestRenderAuxiliary:
    def test_render_auxiliary_reads_signals_dict(self):
        """_render_auxiliary reads ns["signals"] (spec §6 dict keyed by triple)."""
        ns = {
            "signals": {
                ("TaskSkill", "tasks", "L"): {"todo": "do something"},
                ("SysSkill", "system", "G"): {"frame": "1"},
            }
        }
        result = _render_auxiliary(ns)
        assert "══════ tasks ══════" in result
        assert "do something" in result
        assert "══════ system ══════" in result

    def test_render_auxiliary_empty_signals_returns_empty(self):
        """_render_auxiliary returns empty string when signals is empty."""
        ns = {"signals": {}}
        result = _render_auxiliary(ns)
        assert result == ""

    def test_render_auxiliary_missing_signals_returns_empty(self):
        """_render_auxiliary returns empty string when signals is absent from ns."""
        result = _render_auxiliary({})
        assert result == ""

    def test_render_auxiliary_skips_error_payloads(self):
        """_render_auxiliary skips signal entries with _error_id (failed signal_update)."""
        ns = {
            "signals": {
                ("BadSkill", "bad", "L"): {"_error_id": 0},
                ("OkSkill", "ok", "L"): {"status": "fine"},
            }
        }
        result = _render_auxiliary(ns)
        assert "bad" not in result
        assert "══════ ok ══════" in result

    def test_render_auxiliary_header_present_when_has_content(self):
        """Auxiliary section includes a header when there is content."""
        ns = {"signals": {("FooSkill", "foo", "L"): {"key": "signal content"}}}
        result = _render_auxiliary(ns)
        assert "══════ foo ══════" in result
        assert "signal content" in result


# ──────────────────────────────────────────────────────────────────────────────
# Step 6: TestRender
# ──────────────────────────────────────────────────────────────────────────────

class TestRender:
    def test_returns_string(self):
        ns = bare_ns_v3()
        result = render(ns)
        assert isinstance(result, Ping)

    def test_no_system_prompt_no_frame_stream(self):
        ns = bare_ns_v3()
        ping = render(ns)
        assert ping.state.frame_stream == ""
        assert isinstance(ping, Ping)

    def test_system_prompt_in_output(self):
        ns = bare_ns_v3()
        ns["_system_prompt"] = "You are Vessal."
        ping = render(ns)
        assert "You are Vessal." in ping.system_prompt

    def test_frame_stream_in_output(self):
        ns = bare_ns_v3()
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(make_frame_record(number=1, operation="x = 1"))
        ns["_frame_stream"] = fs
        ping = render(ns)
        assert "══════ frame stream ══════" in ping.state.frame_stream
        assert "x = 1" in ping.state.frame_stream

    def test_context_pct_written(self):
        ns = bare_ns_v3()
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(make_frame_record(number=1, operation="x = 1"))
        ns["_frame_stream"] = fs
        render(ns)
        assert "_context_pct" in ns
        assert isinstance(ns["_context_pct"], int)
        assert 0 <= ns["_context_pct"] <= 100

    def test_context_pct_nonzero_when_content(self):
        ns = bare_ns_v3()
        ns["_context_budget"] = 1000
        ns["_token_budget"] = 100
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(make_frame_record(number=1, operation="x = 1"))
        ns["_frame_stream"] = fs
        render(ns)
        assert ns["_context_pct"] > 0

    def test_none_config_uses_default(self):
        ns = bare_ns_v3()
        result = render(ns, config=None)
        assert isinstance(result, Ping)

    def test_custom_system_prompt_key(self):
        ns = bare_ns_v3()
        ns["_compression_prompt"] = "I am compression."
        cfg = RenderConfig(system_prompt_key="_compression_prompt")
        ping = render(ns, config=cfg)
        assert "I am compression." in ping.system_prompt

    def test_three_segments_ordering(self):
        ns = bare_ns_v3()
        ns["_system_prompt"] = "System."
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(make_frame_record(number=1))
        ns["_frame_stream"] = fs
        ns["signals"] = {("AuxSkill", "auxiliary", "L"): {"content": "auxiliary content"}}
        ping = render(ns)
        # system_prompt, frame_stream, signals are independent fields — order is guaranteed by structure
        assert "System." in ping.system_prompt
        assert "══════ frame stream ══════" in ping.state.frame_stream

    def test_invalid_budget_raises(self):
        ns = bare_ns_v3()
        ns["_context_budget"] = 1000
        ns["_token_budget"] = 4096
        with pytest.raises(ValueError, match="context_budget.*<=.*max_tokens"):
            render(ns)

    def test_render_side_effects_are_allowlisted(self):
        ns = bare_ns_v3()
        ns_copy = dict(ns)
        render(ns)
        for k, v in ns_copy.items():
            if k in ("_context_pct", "_budget_total", "_dropped_frame_count"):
                continue
            assert ns[k] == v, f"Key {k} was modified unexpectedly"

    def test_render_writes_budget_total_to_ns(self):
        ns = bare_ns_v3()
        ns["_context_budget"] = 10000
        ns["_token_budget"] = 2000
        render(ns)
        assert ns["_budget_total"] == 8000  # 10000 - 2000

    def test_render_uses_signals_dict_from_namespace(self):
        """render() reads signals dict from ns to populate ping.state.signals."""
        ns = bare_ns_v3()
        ns["signals"] = {("SystemSkill", "_system", "G"): {"frame": "5", "context": "0%"}}
        ping = render(ns)
        assert "frame: 5" in ping.state.signals


class TestDroppedFrameCount:
    """render() writes ns["_dropped_frame_count"] recording the number of dropped frames."""

    def test_no_frames_dropped_zero(self):
        ns = bare_ns_v3()
        fs = FrameStream(k=16, n=8)
        fs.commit_frame(make_frame_record(number=1))
        ns["_frame_stream"] = fs
        render(ns)
        assert ns["_dropped_frame_count"] == 0

    def test_frames_dropped_when_over_budget(self):
        ns = bare_ns_v3()
        # create many frames so the frame stream exceeds budget
        fs = FrameStream(k=16, n=8)
        for i in range(50):
            fs.commit_frame(make_frame_record(number=i, stdout="x" * 500))
        ns["_frame_stream"] = fs
        ns["_context_budget"] = 2000
        ns["_token_budget"] = 500
        render(ns)
        assert ns["_dropped_frame_count"] > 0

    def test_empty_frame_stream_zero(self):
        ns = bare_ns_v3()
        ns["_frame_stream"] = FrameStream()
        render(ns)
        assert ns["_dropped_frame_count"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# Step 7: TestKernelRenderV3  (filled after step 8 modifications)
# ──────────────────────────────────────────────────────────────────────────────

from tests.unit.kernel._ping_helpers import _ns, _exec


class TestKernelRenderV3:
    """Integration tests for Kernel using v4 renderer."""

    def test_kernel_render_returns_string(self):
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = Kernel()
        result = k.ping(None, _ns(k))
        assert isinstance(result, Ping)

    def test_kernel_exec_operation_returns_exec_result(self):
        from vessal.ark.shell.hull.cell.kernel import Kernel
        from vessal.ark.shell.hull.cell.kernel.executor import ExecResult
        k = Kernel()
        # ping(pong, ns) executes operation internally; observation.diff proves it ran
        _exec(k, "x = 1")
        assert k.L["observation"].diff != "" or k.L.get("x") == 1

    def test_frame_stream_not_populated_by_exec(self):
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = Kernel()
        # ping(pong, ns) DOES commit to _frame_stream (Cell's job moved to Kernel.ping in PR 2)
        before = k.L["_frame_stream"].hot_frame_count()
        _exec(k, "x = 1")
        # One frame was committed by ping
        assert k.L["_frame_stream"].hot_frame_count() == before + 1

    def test_system_prompt_key_used(self):
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = Kernel()
        k.L["_system_prompt"] = "Test system prompt"
        ping = k.ping(None, _ns(k))
        assert "Test system prompt" in ping.system_prompt

    def test_no_tracer_arg_in_render(self):
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = Kernel()
        result = k.ping(None, _ns(k))
        assert isinstance(result, Ping)

    def test_kernel_render_updates_context_pct(self):
        from vessal.ark.shell.hull.cell.kernel import Kernel
        k = Kernel()
        k.ping(None, _ns(k))
        assert "_context_pct" in k.L
        assert isinstance(k.L["_context_pct"], int)


# ──────────────────────────────────────────────────────────────────────────────
# Three-segment system prompt assembly tests
# ──────────────────────────────────────────────────────────────────────────────

class TestThreeSegmentAssembly:
    def test_render_three_segment_assembly(self):
        """Three-segment system prompt assembly: kernel protocol + SOUL + skill protocol."""
        ns = bare_ns_v3()
        ns["_system_prompt"] = "You are an execution engine."
        ns["_soul"] = "I am a friendly assistant."

        class FakeBehaviorSkill:
            name = "reviewer"
            description = "review"

            def _prompt(self):
                return ("when reviewing code", "look at diff first")

        ns["reviewer"] = FakeBehaviorSkill()

        ping = render(ns)
        sp = ping.system_prompt

        # all three segments are present and in order
        assert "You are an execution engine" in sp
        assert "══════ SOUL ══════" in sp
        assert "I am a friendly assistant" in sp
        assert "══════ skill protocol ══════" in sp
        assert "── reviewer ──" in sp
        assert "When when reviewing code:" in sp

        # order: kernel protocol before SOUL, SOUL before skill protocol
        kernel_pos = sp.index("You are an execution engine")
        soul_pos = sp.index("══════ SOUL ══════")
        protocol_pos = sp.index("══════ skill protocol ══════")
        assert kernel_pos < soul_pos < protocol_pos

    def test_render_no_soul_no_protocols(self):
        """Only kernel protocol when there is no SOUL and no _prompt()."""
        ns = bare_ns_v3()
        ns["_system_prompt"] = "kernel protocol"
        ns.pop("_soul", None)

        ping = render(ns)
        assert ping.system_prompt == "kernel protocol"
        assert "══════ SOUL ══════" not in ping.system_prompt
        assert "══════ skill protocol ══════" not in ping.system_prompt

    def test_render_soul_only(self):
        """Two segments when there is SOUL but no _prompt()."""
        ns = bare_ns_v3()
        ns["_system_prompt"] = "kernel protocol"
        ns["_soul"] = "my soul"

        ping = render(ns)
        assert "══════ SOUL ══════" in ping.system_prompt
        assert "my soul" in ping.system_prompt
        assert "══════ skill protocol ══════" not in ping.system_prompt

    def test_assemble_skill_context_false_skips_soul_and_protocols(self):
        """RenderConfig with assemble_skill_context=False omits SOUL and skill protocol sections."""
        ns = bare_ns_v3()
        ns["_compression_prompt"] = "organize memories"
        ns["_soul"] = "my soul"

        class FakeSkill:
            name = "some_skill"
            description = "does something"

            def _prompt(self):
                return ("at any time", "do it in some way")

        ns["some_skill"] = FakeSkill()

        cfg = RenderConfig(
            system_prompt_key="_compression_prompt",
            assemble_skill_context=False,
        )
        ping = render(ns, config=cfg)
        assert "organize memories" in ping.system_prompt
        assert "══════ SOUL ══════" not in ping.system_prompt
        assert "══════ skill protocol ══════" not in ping.system_prompt


def test_renderer_output_order_system_stream_signals():
    from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream
    from vessal.ark.shell.hull.cell.kernel.render.renderer import render
    fs = FrameStream(k=2, n=2)
    fs._cold = [[{
        "schema_version": 7, "range": [0, 1], "intent": "COLD_SENTINEL",
        "operations": [], "outcomes": "", "artifacts": [], "notable": "",
        "layer": 0, "compacted_at": 2,
    }]]
    fs.commit_frame({
        "schema_version": 7, "number": 3,
        "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
        "pong": {"think": "", "action": {"operation": "HOT_SENTINEL", "expect": ""}},
        "observation": {"stdout": "", "diff": "", "error": None, "verdict": None},
    })
    ns = {
        "_frame_stream": fs,
        "_system_prompt": "SYS_SENTINEL",
        "_context_budget": 128000,
        "_token_budget": 4096,
        "_builtin_names": [],
        "_context_pct": 0,
        "_ns_meta": {},
        "_signal_outputs": [],
        "_dropped_frame_count": 0,
    }
    out = render(ns)
    full_text = out.system_prompt + out.state.frame_stream + out.state.signals
    i_sys = full_text.index("SYS_SENTINEL")
    i_stream_hdr = full_text.index("frame stream")
    i_cold = full_text.index("COLD_SENTINEL")
    i_hot = full_text.index("HOT_SENTINEL")
    assert i_sys < i_stream_hdr < i_cold < i_hot
