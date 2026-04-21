# test_core.py — Core module tests
#
# parser tests: pure functions, tested directly.
# core tests: mock openai.OpenAI, verify call arguments and return value handling.

import os
from unittest.mock import MagicMock, patch

import pytest
from openai import (
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
    AuthenticationError,
    PermissionDeniedError,
    BadRequestError,
)

from vessal.ark.shell.hull.cell.core.parser import ParseError, parse_response
from vessal.ark.shell.hull.cell.core import Core
from vessal.ark.shell.hull.cell.protocol import Ping, Pong, State, Action


# ============================================================
# parse_response tests
# ============================================================


class TestParseResponse:
    """Pure function tests for parse_response."""

    def test_normal_with_think(self):
        """Normal response: contains think and action, Pong fields are correct."""
        text = "<think>analysis</think>\n<action>\nx = 1\n</action>"
        pong = parse_response(text)
        assert pong.action.operation == "x = 1"
        assert pong.think == "analysis"
        assert pong.action.expect == ""

    def test_action_only(self):
        """Only action tag present; think and expect are empty strings."""
        text = "<action>x = 1</action>"
        pong = parse_response(text)
        assert pong.action.operation == "x = 1"
        assert pong.think == ""
        assert pong.action.expect == ""

    def test_all_three_tags(self):
        """All three tags present, all parsed correctly."""
        text = "<think>thinking</think><action>y = 2</action><expect>assert y == 2</expect>"
        pong = parse_response(text)
        assert pong.think == "thinking"
        assert pong.action.operation == "y = 2"
        assert pong.action.expect == "assert y == 2"

    def test_multiline_operation(self):
        """Multi-line operation code is parsed correctly."""
        text = "<action>\nx = 1\ny = 2\nz = x + y\n</action>"
        pong = parse_response(text)
        assert pong.action.operation == "x = 1\ny = 2\nz = x + y"

    def test_indented_code_in_action(self):
        """Code with indentation is parsed correctly."""
        text = "<action>\ndef foo():\n    return 42\n</action>"
        pong = parse_response(text)
        assert pong.action.operation == "def foo():\n    return 42"

    def test_nested_angle_brackets_in_code(self):
        """< > symbols in code do not interfere with parsing."""
        text = '<action>\nif x < 10 and y > 5:\n    pass\n</action>'
        pong = parse_response(text)
        assert "if x < 10 and y > 5" in pong.action.operation

    def test_raises_when_action_missing(self):
        """ParseError raised when <action> is missing."""
        with pytest.raises(ParseError, match="No <action>"):
            parse_response("text with no tags")

    def test_raises_when_action_missing_only_think(self):
        """Only think tag, no action — ParseError raised."""
        with pytest.raises(ParseError):
            parse_response("<think>I am thinking but taking no action</think>")

    def test_raises_when_action_empty(self):
        """ParseError raised when <action> content is whitespace."""
        with pytest.raises(ParseError, match="empty"):
            parse_response("<action>  </action>")

    def test_raises_when_action_whitespace_only(self):
        """ParseError raised when <action> content is only newlines/whitespace."""
        with pytest.raises(ParseError):
            parse_response("<action>\n   \n</action>")

    def test_duplicate_action_takes_last(self):
        """When <action> is duplicated, the last one is used (reasoning model tolerance)."""
        text = "<action>first</action>\n<action>second</action>"
        pong = parse_response(text)
        assert pong.action.operation == "second"

    def test_duplicate_think_takes_last(self):
        """When <think> is duplicated, the last one is used."""
        text = "<think>a</think><think>b</think><action>pass</action>"
        pong = parse_response(text)
        assert pong.think == "b"

    def test_duplicate_expect_takes_last(self):
        """When <expect> is duplicated, the last one is used."""
        text = "<action>pass</action><expect>assert True</expect><expect>assert False</expect>"
        pong = parse_response(text)
        assert pong.action.expect == "assert False"

    def test_empty_string_raises(self):
        """Empty string has no action — ParseError raised."""
        with pytest.raises(ParseError):
            parse_response("")

    def test_parse_error_is_value_error(self):
        """ParseError is a subclass of ValueError."""
        assert issubclass(ParseError, ValueError)

    def test_returns_pong_type(self):
        """Return value is a Pong instance."""
        pong = parse_response("<action>x = 1</action>")
        assert isinstance(pong, Pong)


# ============================================================
# Core tests
# ============================================================


def _make_mock_response(content: str, model: str = "test-model") -> MagicMock:
    """Construct a mock OpenAI API response object."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 20
    response = MagicMock()
    response.choices = [choice]
    response.model = model
    response.usage = usage
    return response


def _make_ping(**kwargs) -> Ping:
    """Construct a test Ping (system→LLM perceptual input) with default values."""
    system_prompt = kwargs.get("system_prompt", "You are an agent.")
    frame_stream = kwargs.get("frame_stream", "══════ frame stream ══════")
    signals = kwargs.get("signals", "goal: test")
    return Ping(system_prompt=system_prompt, state=State(frame_stream=frame_stream, signals=signals))


class TestCore:
    """Core class tests with mocked OpenAI API."""

    @patch.dict(os.environ, {"OPENAI_MODEL": "test-model"})
    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_step_calls_api_correctly(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_mock_response(
            "<think>thinking</think>\n<action>\nx = 1\n</action>"
        )

        core = Core(api_params={"temperature": 0.5, "max_tokens": 2048})
        ping = _make_ping(system_prompt="sys", frame_stream="frames", signals="")
        pong, _, _ = core.step(ping)

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "test-model"
        assert call_args.kwargs["temperature"] == 0.5
        assert call_args.kwargs["max_tokens"] == 2048
        assert isinstance(pong, Pong)

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_step_returns_pong(self, mock_openai_cls):
        """Core.step() returns a Pong."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_mock_response(
            "<action>y = 2 + 3</action>"
        )

        core = Core()
        pong, _, _ = core.step(_make_ping())
        assert isinstance(pong, Pong)
        assert pong.action.operation == "y = 2 + 3"

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_step_empty_response(self, mock_openai_cls):
        """Core.step() raises ValueError when response content is None (no action tag)."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        message = MagicMock()
        message.content = None
        choice = MagicMock()
        choice.message = message
        response = MagicMock()
        response.choices = [choice]
        response.model = "test-model"
        response.usage = None
        mock_client.chat.completions.create.return_value = response

        core = Core()
        with pytest.raises(ValueError):
            core.step(_make_ping())

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_client_created_with_timeout(self, mock_openai_cls):
        """OpenAI() is passed the timeout parameter; other config comes from env vars."""
        Core()
        mock_openai_cls.assert_called_once_with(timeout=60.0)

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_client_created_with_custom_timeout(self, mock_openai_cls):
        """Custom timeout parameter is forwarded to the OpenAI client."""
        Core(timeout=120.0)
        mock_openai_cls.assert_called_once_with(timeout=120.0)

    @patch.dict(os.environ, {"OPENAI_MODEL": "custom-model"})
    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_model_from_env(self, mock_openai_cls):
        core = Core()
        assert core._model == "custom-model"

    @patch.dict(os.environ, {}, clear=False)
    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_default_parameters(self, mock_openai_cls):
        os.environ.pop("OPENAI_MODEL", None)
        core = Core()
        assert core._model == "gpt-4o"
        assert core._api_params["temperature"] == 0.7
        assert core._api_params["max_tokens"] == 4096

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_system_and_user_messages_sent(self, mock_openai_cls):
        """step(ping) sends system + user messages."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_mock_response(
            "<action>pass</action>"
        )

        core = Core()
        ping = _make_ping(
            system_prompt="You are an agent.",
            frame_stream="══════ frame stream ══════",
            signals="goal: test",
        )
        core.step(ping)

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are an agent."
        assert messages[1]["role"] == "user"
        assert "══════ frame stream ══════" in messages[1]["content"]
        assert "goal: test" in messages[1]["content"]

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_messages_sent_every_call(self, mock_openai_cls):
        """Multiple consecutive step() calls each carry system + user messages."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_mock_response(
            "<action>pass</action>"
        )

        core = Core()
        core.step(_make_ping(frame_stream="state 1"))
        core.step(_make_ping(frame_stream="state 2"))

        for call in mock_client.chat.completions.create.call_args_list:
            messages = call.kwargs["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"


# ============================================================
# Network robustness tests
# ============================================================


class TestCoreResilience:
    """Core network robustness: timeouts, retries, error classification."""

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_default_timeout(self, mock_openai_cls):
        """Default timeout is 60.0."""
        Core()
        mock_openai_cls.assert_called_once_with(timeout=60.0)

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_custom_timeout(self, mock_openai_cls):
        """Custom timeout is forwarded to the OpenAI client."""
        Core(timeout=120.0)
        mock_openai_cls.assert_called_once_with(timeout=120.0)

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_default_max_retries(self, mock_openai_cls):
        """Default max_retries is 3."""
        core = Core()
        assert core._max_retries == 3

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_custom_max_retries(self, mock_openai_cls):
        """Custom max_retries takes effect."""
        core = Core(max_retries=5)
        assert core._max_retries == 5

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_retry_on_timeout(self, mock_openai_cls):
        """APITimeoutError triggers retry; eventually succeeds and returns Pong."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        # First two attempts time out, third succeeds
        mock_client.chat.completions.create.side_effect = [
            APITimeoutError("timeout"),
            APITimeoutError("timeout"),
            _make_mock_response("<action>x = 1</action>"),
        ]

        core = Core(max_retries=2)
        pong, _, _ = core.step(_make_ping())

        assert isinstance(pong, Pong)
        assert pong.action.operation == "x = 1"
        assert mock_client.chat.completions.create.call_count == 3

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_retry_exhausted_raises(self, mock_openai_cls):
        """Raises the last exception after retries are exhausted."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = APITimeoutError("timeout")

        core = Core(max_retries=2)
        with pytest.raises(APITimeoutError):
            core.step(_make_ping())

        # Initial attempt + 2 retries = 3 total calls
        assert mock_client.chat.completions.create.call_count == 3

    def _make_api_error(self, error_cls, message):
        """Construct an OpenAI API error exception."""
        mock_response = MagicMock()
        mock_response.request = MagicMock()
        return error_cls(message, response=mock_response, body=None)

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_no_retry_on_auth_error(self, mock_openai_cls):
        """AuthenticationError is raised immediately without retrying."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = self._make_api_error(
            AuthenticationError, "invalid key"
        )

        core = Core(max_retries=3)
        with pytest.raises(AuthenticationError):
            core.step(_make_ping())

        # Called only once, no retries
        assert mock_client.chat.completions.create.call_count == 1

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_no_retry_on_permission_error(self, mock_openai_cls):
        """PermissionDeniedError is raised immediately without retrying."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = self._make_api_error(
            PermissionDeniedError, "access denied"
        )

        core = Core(max_retries=3)
        with pytest.raises(PermissionDeniedError):
            core.step(_make_ping())

        assert mock_client.chat.completions.create.call_count == 1

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_no_retry_on_bad_request(self, mock_openai_cls):
        """BadRequestError is raised immediately without retrying."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = self._make_api_error(
            BadRequestError, "prompt too long"
        )

        core = Core(max_retries=3)
        with pytest.raises(BadRequestError):
            core.step(_make_ping())

        assert mock_client.chat.completions.create.call_count == 1

    def _make_connection_error(self, message):
        """Construct an APIConnectionError."""
        mock_request = MagicMock()
        return APIConnectionError(message=message, request=mock_request)

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_retry_on_connection_error(self, mock_openai_cls):
        """APIConnectionError triggers retry and returns Pong."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = [
            self._make_connection_error("connection failed"),
            _make_mock_response("<action>pass</action>"),
        ]

        core = Core(max_retries=1)
        pong, _, _ = core.step(_make_ping())

        assert isinstance(pong, Pong)
        assert pong.action.operation == "pass"
        assert mock_client.chat.completions.create.call_count == 2

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_retry_on_server_error(self, mock_openai_cls):
        """InternalServerError triggers retry and returns Pong."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = [
            self._make_api_error(InternalServerError, "server overloaded"),
            _make_mock_response("<action>pass</action>"),
        ]

        core = Core(max_retries=1)
        pong, _, _ = core.step(_make_ping())

        assert isinstance(pong, Pong)
        assert pong.action.operation == "pass"
        assert mock_client.chat.completions.create.call_count == 2


# ============================================================
# Ping interface tests
# ============================================================


@patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
def test_core_step_accepts_ping(mock_openai_cls):
    """Core.step() accepts a Ping and returns a Pong."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_mock_response(
        "<think>thinking</think>\n<action>x = 1</action>"
    )

    core = Core()
    ping = Ping(
        system_prompt="You are an agent.",
        state=State(frame_stream="══════ frame stream ══════", signals="goal: test"),
    )
    pong, _, _ = core.step(ping)
    assert isinstance(pong, Pong)
    assert isinstance(pong.action, Action)


@patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
def test_core_step_ping_builds_system_and_user_messages(mock_openai_cls):
    """step(ping) sends system + user messages whose content comes from ping fields."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_mock_response(
        "<action>pass</action>"
    )

    core = Core()
    ping = Ping(
        system_prompt="You are an agent.",
        state=State(frame_stream="══════ frame stream ══════", signals="goal: test"),
    )
    core.step(ping)

    call_args = mock_client.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are an agent."
    assert messages[1]["role"] == "user"
    assert "══════ frame stream ══════" in messages[1]["content"]
    assert "goal: test" in messages[1]["content"]


@patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
def test_core_step_pong_parsed_correctly(mock_openai_cls):
    """core.step() returns a Pong with the correct action.operation field."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_mock_response(
        "<think>analysis</think>\n<action>x = 42</action>"
    )

    core = Core()
    ping = Ping(system_prompt="sys", state=State(frame_stream="frames", signals=""))
    pong, _, _ = core.step(ping)
    assert pong.action.operation == "x = 42"
    assert pong.think == "analysis"


# ============================================================
# Core.step() usage tuple return tests
# ============================================================


class TestCoreUsageReturn:
    """Core.step() returns (Pong, prompt_tokens, completion_tokens)."""

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_returns_usage_tuple(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        resp = _make_mock_response("<action>x = 1</action>")
        resp.usage.prompt_tokens = 5000
        resp.usage.completion_tokens = 200
        mock_client.chat.completions.create.return_value = resp

        core = Core()
        pong, pt, ct = core.step(_make_ping())
        assert isinstance(pong, Pong)
        assert pt == 5000
        assert ct == 200

    @patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI")
    def test_returns_none_when_no_usage(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        resp = _make_mock_response("<action>x = 1</action>")
        resp.usage = None
        mock_client.chat.completions.create.return_value = resp

        core = Core()
        pong, pt, ct = core.step(_make_ping())
        assert isinstance(pong, Pong)
        assert pt is None
        assert ct is None
