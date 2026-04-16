"""Audio transcription via 302AI GLM-ASR-2512."""

import base64
import json
import os
import urllib.error
import urllib.request

from vessal.ark.shell.hull.skill import SkillBase


class Audio(SkillBase):
    name = "audio"
    description = "audio transcription"

    _BASE = "https://api.302.ai"

    def __init__(self):
        super().__init__()
        self._api_key = os.environ.get("API_302AI_KEY", "")

    def transcribe(self, file_path: str) -> str:
        """Transcribe an audio file to text. Supports wav/mp3, ≤30 seconds, ≤25 MB."""
        if not self._api_key:
            raise RuntimeError("Environment variable API_302AI_KEY is not set")
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        size = os.path.getsize(file_path)
        if size > 25 * 1024 * 1024:
            raise ValueError(f"File exceeds 25 MB limit: {size / 1024 / 1024:.1f} MB")

        with open(file_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()

        payload = json.dumps({
            "file_base64": audio_b64,
            "model": "glm-asr-2512",
        }).encode()
        req = urllib.request.Request(
            f"{self._BASE}/bigmodel/api/paas/v4/audio/transcriptions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # longer timeout: uploading base64 audio
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:200]
            raise RuntimeError(f"HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}") from e

        text = data.get("text", "")
        print(f"[audio] transcribed {os.path.basename(file_path)} → {len(text)} chars")
        return text.strip()
