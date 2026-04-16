# tests/skills/test_vision.py
"""Vision skill unit tests."""

import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from vessal.skills.vision.skill import Vision


class TestVisionSkill:
    def test_name_and_description(self):
        v = Vision()
        assert v.name == "vision"
        assert isinstance(v.description, str)
        # SkillBase contract: description should be concise (≤ 30 characters for English)
        assert len(v.description) <= 30, "description exceeds 30 characters, violates SkillBase contract"

    def test_ask_file_not_found(self):
        v = Vision()
        with pytest.raises(FileNotFoundError, match="Image not found"):
            v.ask("/nonexistent/path.png", "describe this")

    def test_ask_returns_answer(self):
        v = Vision()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n")
            tmp_path = f.name
        try:
            mock_msg = MagicMock()
            mock_msg.content = "This is a bar chart"
            mock_choice = MagicMock()
            mock_choice.message = mock_msg
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]

            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_resp
            v._client = mock_client

            result = v.ask(tmp_path, "What kind of chart is this?")
            assert result == "This is a bar chart"

            call_kwargs = mock_client.chat.completions.create.call_args
            assert call_kwargs[1]["model"] == "qwen_3_vl_235b_a22b_awq_int4"
            messages = call_kwargs[1]["messages"]
            assert messages[0]["content"][0]["type"] == "image_url"
            assert messages[0]["content"][1]["type"] == "text"
        finally:
            os.unlink(tmp_path)

    def test_describe_delegates_to_ask(self):
        v = Vision()
        with patch.object(v, "ask", return_value="a landscape photo") as mock_ask:
            result = v.describe("/fake/path.png")
        assert result == "a landscape photo"
        mock_ask.assert_called_once_with(
            "/fake/path.png", "Please describe this image in detail."
        )

    def test_ask_raises_on_none_content(self):
        v = Vision()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n")
            tmp_path = f.name
        try:
            mock_msg = MagicMock()
            mock_msg.content = None
            mock_choice = MagicMock()
            mock_choice.message = mock_msg
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_resp
            v._client = mock_client
            with pytest.raises(RuntimeError, match="empty content"):
                v.ask(tmp_path, "test")
        finally:
            os.unlink(tmp_path)

    def test_ask_detects_jpeg_mime(self):
        v = Vision()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"\xff\xd8\xff")
            tmp_path = f.name
        try:
            mock_msg = MagicMock()
            mock_msg.content = "ok"
            mock_choice = MagicMock()
            mock_choice.message = mock_msg
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]

            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_resp
            v._client = mock_client

            v.ask(tmp_path, "test")
            call_kwargs = mock_client.chat.completions.create.call_args
            img_url = call_kwargs[1]["messages"][0]["content"][0]["image_url"]["url"]
            assert img_url.startswith("data:image/jpeg;base64,")
        finally:
            os.unlink(tmp_path)
