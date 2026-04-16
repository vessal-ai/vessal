"""Audio skill unit tests."""

import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from vessal.skills.audio.skill import Audio


def _mock_urlopen(response_data: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_data).encode()
    mock_resp.__enter__ = lambda self: self
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestAudioSkill:
    def test_name_and_description(self):
        a = Audio()
        assert a.name == "audio"
        assert isinstance(a.description, str)
        assert len(a.description) <= 30

    def test_transcribe_missing_key_raises(self):
        a = Audio()
        a._api_key = ""
        with pytest.raises(RuntimeError, match="API_302AI_KEY"):
            a.transcribe("/nonexistent/audio.mp3")

    def test_transcribe_file_not_found(self):
        a = Audio()
        a._api_key = "test-key"
        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            a.transcribe("/nonexistent/audio.mp3")

    def test_transcribe_returns_text(self):
        a = Audio()
        a._api_key = "test-key"
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"fake audio data")
            tmp = f.name
        try:
            fake = {"text": " This is a test audio clip ", "usage": {"total_tokens": 100}}
            with patch("urllib.request.urlopen", return_value=_mock_urlopen(fake)):
                result = a.transcribe(tmp)
            assert result == "This is a test audio clip"
        finally:
            os.unlink(tmp)

    def test_transcribe_empty_text(self):
        a = Audio()
        a._api_key = "test-key"
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"silence")
            tmp = f.name
        try:
            fake = {"text": "", "usage": {"total_tokens": 10}}
            with patch("urllib.request.urlopen", return_value=_mock_urlopen(fake)):
                result = a.transcribe(tmp)
            assert result == ""
        finally:
            os.unlink(tmp)

    def test_transcribe_file_too_large(self):
        a = Audio()
        a._api_key = "test-key"
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            # Truncate to 26MB without writing actual data (sparse file)
            f.seek(26 * 1024 * 1024)
            f.write(b"\x00")
            tmp = f.name
        try:
            with pytest.raises(ValueError, match="25 MB"):
                a.transcribe(tmp)
        finally:
            os.unlink(tmp)

    def test_transcribe_sends_base64(self):
        """Verify the API payload contains base64-encoded audio."""
        a = Audio()
        a._api_key = "test-key"
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"test-audio-bytes")
            tmp = f.name
        try:
            fake = {"text": "ok"}
            with patch("urllib.request.urlopen", return_value=_mock_urlopen(fake)) as mock_open:
                a.transcribe(tmp)
            req_obj = mock_open.call_args[0][0]
            body = json.loads(req_obj.data.decode())
            assert body["model"] == "glm-asr-2512"
            assert "file_base64" in body
            assert len(body["file_base64"]) > 0
        finally:
            os.unlink(tmp)

    def test_transcribe_http_error_raises(self):
        import urllib.error
        a = Audio()
        a._api_key = "test-key"
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio")
            tmp = f.name
        try:
            err = urllib.error.HTTPError(
                url="https://api.302.ai/...", code=400,
                msg="Bad Request", hdrs=None, fp=None
            )
            with patch("urllib.request.urlopen", side_effect=err):
                with pytest.raises(RuntimeError, match="HTTP 400"):
                    a.transcribe(tmp)
        finally:
            os.unlink(tmp)
