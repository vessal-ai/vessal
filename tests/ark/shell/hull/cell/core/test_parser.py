# tests/unit/test_parser.py — parse_response() protocol boundary tests
#
# Coverage:
#   TestParseResponseValid     valid responses in various forms
#   TestParseResponseErrors    error paths for invalid responses

import pytest

from vessal.ark.shell.hull.cell.core.parser import parse_response, ParseError
from vessal.ark.shell.hull.cell.protocol import Pong


# ─────────────────────────────────────────────
# TestParseResponseValid
# ─────────────────────────────────────────────


class TestParseResponseValid:
    """Valid responses parsed into correct Pong fields."""

    def test_all_three_tags_returns_correct_pong_fields(self):
        """Complete response with all three tags; Pong fields are correct."""
        text = (
            "<think>reasoning here</think>\n"
            "<action>x = 1</action>\n"
            "<expect>assert x == 1</expect>"
        )
        pong = parse_response(text)
        assert isinstance(pong, Pong)
        assert pong.think == "reasoning here"
        assert pong.action.operation == "x = 1"
        assert pong.action.expect == "assert x == 1"

    def test_action_only_returns_pong_with_empty_think_and_expect(self):
        """Only <action> tag present; think and expect are empty strings."""
        text = "<action>result = 42</action>"
        pong = parse_response(text)
        assert pong.action.operation == "result = 42"
        assert pong.think == ""
        assert pong.action.expect == ""

    def test_parse_response_no_raw_response(self):
        """Pong has no raw_response field."""
        pong = parse_response("<action>x = 1</action>")
        assert isinstance(pong, Pong)
        assert not hasattr(pong, "raw_response")
        assert pong.action.operation == "x = 1"
        assert pong.think == ""
        assert pong.action.expect == ""

    def test_parse_response_with_all_tags(self):
        """All three tags present; all fields populated correctly."""
        text = "<think>analyzing</think>\n<action>y = 2</action>\n<expect>assert y == 2</expect>"
        pong = parse_response(text)
        assert pong.think == "analyzing"
        assert pong.action.operation == "y = 2"
        assert pong.action.expect == "assert y == 2"

    def test_text_outside_tags_is_ignored(self):
        """Text outside tags does not appear in any Pong field (think/operation/expect)."""
        text = "OUTSIDE TEXT\n<action>y = 2</action>\nMORE OUTSIDE"
        pong = parse_response(text)
        assert pong.action.operation == "y = 2"
        assert pong.think == ""
        assert pong.action.expect == ""
        # outside text must not leak into any structured field
        assert "OUTSIDE TEXT" not in pong.think
        assert "OUTSIDE TEXT" not in pong.action.operation
        assert "OUTSIDE TEXT" not in pong.action.expect
        assert "MORE OUTSIDE" not in pong.think
        assert "MORE OUTSIDE" not in pong.action.operation
        assert "MORE OUTSIDE" not in pong.action.expect


# ─────────────────────────────────────────────
# TestParseResponseErrors
# ─────────────────────────────────────────────


class TestParseResponseErrors:
    """Invalid responses raise ParseError."""

    def test_missing_action_raises_parse_error(self):
        """ParseError raised when no <action> tag is present."""
        text = "<think>some thought</think>"
        with pytest.raises(ParseError):
            parse_response(text)

    def test_empty_action_content_raises_parse_error(self):
        """ParseError raised when <action> content is pure whitespace."""
        text = "<action>   </action>"
        with pytest.raises(ParseError):
            parse_response(text)

    def test_duplicate_action_takes_last(self):
        """When <action> is duplicated, the last one is used."""
        text = "<action>x = 1</action><action>y = 2</action>"
        pong = parse_response(text)
        assert pong.action.operation == "y = 2"

    def test_duplicate_think_takes_last(self):
        """When <think> is duplicated, the last one is used."""
        text = "<think>a</think><think>b</think><action>pass</action>"
        pong = parse_response(text)
        assert pong.think == "b"

    def test_duplicate_expect_takes_last(self):
        """When <expect> is duplicated, the last one is used."""
        text = "<action>pass</action><expect>assert 1</expect><expect>assert 2</expect>"
        pong = parse_response(text)
        assert pong.action.expect == "assert 2"
