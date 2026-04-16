# tests/skills/test_search.py
"""Search skill unit tests."""

import json
from unittest.mock import patch, MagicMock

import pytest

from vessal.skills.search.skill import Search


def _mock_urlopen(response_data: dict):
    """Create a mock for urllib.request.urlopen context manager."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_data).encode()
    mock_resp.__enter__ = lambda self: self
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestSearchSkill:
    def test_name_and_description(self):
        s = Search()
        assert s.name == "search"
        assert isinstance(s.description, str)
        assert len(s.description) <= 30

    def test_web_missing_key_raises(self):
        s = Search()
        s._api_key = ""
        with pytest.raises(RuntimeError, match="API_302AI_KEY"):
            s.web("test query")

    def test_read_missing_key_raises(self):
        s = Search()
        s._api_key = ""
        with pytest.raises(RuntimeError, match="API_302AI_KEY"):
            s.read("https://example.com")

    def test_web_returns_parsed_results(self):
        s = Search()
        s._api_key = "test-key"
        fake = {
            "code": 0,
            "data": {
                "webPages": [
                    {
                        "name": "Result 1",
                        "url": "https://a.com",
                        "snippet": "snippet1",
                        "summary": "summary1",
                    },
                    {
                        "name": "Result 2",
                        "url": "https://b.com",
                        "snippet": "snippet2",
                        "summary": "summary2",
                    },
                ],
                "images": [],
            },
            "message": "OK",
        }
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(fake)):
            results = s.web("test", count=2)
        assert len(results) == 2
        assert results[0]["name"] == "Result 1"
        assert results[0]["url"] == "https://a.com"
        assert results[1]["summary"] == "summary2"

    def test_web_api_error_raises(self):
        s = Search()
        s._api_key = "test-key"
        fake = {"code": 1, "message": "rate limited"}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(fake)):
            with pytest.raises(RuntimeError, match="Search failed"):
                s.web("test")

    def test_web_empty_results(self):
        s = Search()
        s._api_key = "test-key"
        fake = {"code": 0, "data": {"webPages": [], "images": []}, "message": "OK"}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(fake)):
            results = s.web("obscure query")
        assert results == []

    def test_read_returns_content(self):
        s = Search()
        s._api_key = "test-key"
        fake = {"data": "# Page Title\n\nSome content here."}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(fake)):
            content = s.read("https://example.com")
        assert "Page Title" in content

    def test_read_string_response(self):
        """Web-Reader may return a plain string."""
        s = Search()
        s._api_key = "test-key"
        fake = {"data": "plain text content"}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(fake)):
            content = s.read("https://example.com")
        assert content == "plain text content"

    def test_read_api_error_raises(self):
        s = Search()
        s._api_key = "test-key"
        fake = {"code": 1, "message": "invalid url"}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(fake)):
            with pytest.raises(RuntimeError, match="Read failed"):
                s.read("https://example.com")

    def test_web_http_error_raises(self):
        import urllib.error
        s = Search()
        s._api_key = "test-key"
        err = urllib.error.HTTPError(
            url="https://api.302.ai/...", code=429,
            msg="Too Many Requests", hdrs=None, fp=None
        )
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(RuntimeError, match="HTTP 429"):
                s.web("test")

    def test_web_url_error_raises(self):
        import urllib.error
        s = Search()
        s._api_key = "test-key"
        err = urllib.error.URLError(reason="Connection refused")
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(RuntimeError, match="Network error"):
                s.web("test")
