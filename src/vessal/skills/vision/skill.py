"""Image understanding via Qwen3 VL."""

import base64
import os

from vessal.ark.shell.hull.skill import SkillBase


class Vision(SkillBase):
    name = "vision"
    description = "image understanding"

    def __init__(self):
        super().__init__()
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=os.environ.get("VISION_API_KEY", "sk-wx"),
                base_url=os.environ.get("VISION_BASE_URL", "http://192.168.40.42:8001/v1"),
            )
        return self._client

    def describe(self, image_path: str) -> str:
        """Describe the contents of an image."""
        return self.ask(image_path, "Please describe this image in detail.")

    def ask(self, image_path: str, question: str) -> str:
        """Ask a question about an image and return the answer."""
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        ext = os.path.splitext(image_path)[1].lower().lstrip(".")
        mime_map = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
        }
        mime = mime_map.get(ext, "image/png")

        client = self._get_client()
        resp = client.chat.completions.create(
            model="qwen_3_vl_235b_a22b_awq_int4",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {
                        "url": f"data:{mime};base64,{img_b64}",
                    }},
                    {"type": "text", "text": question},
                ],
            }],
        )
        answer = resp.choices[0].message.content
        if answer is None:
            raise RuntimeError("vision: model returned empty content (choices[0].message.content is None)")
        print(f"[vision] {question[:40]}{'...' if len(question) > 40 else ''} → {answer[:80]}{'...' if len(answer) > 80 else ''}")
        return answer
