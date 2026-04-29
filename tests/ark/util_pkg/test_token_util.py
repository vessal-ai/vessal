"""test_token_util.py — Unit tests for estimate_tokens."""

from vessal.ark.util.token_util import estimate_tokens


class TestEstimateTokens:
    def test_empty_string(self) -> None:
        assert estimate_tokens("") == 0

    def test_ascii_short(self) -> None:
        # "hello" = 5 bytes / 4 = 1
        assert estimate_tokens("hello") == 1

    def test_ascii_exact_boundary(self) -> None:
        # 4 bytes / 4 = 1
        assert estimate_tokens("abcd") == 1

    def test_chinese(self) -> None:
        # "你好" = 6 bytes in UTF-8 / 4 = 1
        assert estimate_tokens("你好") == 1

    def test_longer_ascii(self) -> None:
        text = "a" * 400  # 400 bytes / 4 = 100
        assert estimate_tokens(text) == 100

    def test_returns_int(self) -> None:
        assert isinstance(estimate_tokens("test"), int)

    def test_monotone_with_length(self) -> None:
        # Longer text should never produce a smaller estimate than shorter text
        assert estimate_tokens("a" * 8) >= estimate_tokens("a" * 4)

    def test_multiline(self) -> None:
        text = "line1\nline2\nline3"
        # 17 bytes / 4 = 4
        assert estimate_tokens(text) == 4
