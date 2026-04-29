"""Regression test: the chat UI's outbox calls must carry ?after= (data plane contract)."""
from pathlib import Path
import re


def test_chat_ui_calls_outbox_with_after():
    ui_js = Path(__file__).resolve().parents[3] / "src" / "vessal" / "skills" / "chat" / "ui" / "app.js"
    text = ui_js.read_text(encoding="utf-8")
    outbox_calls = re.findall(r"fetch\([^)]*outbox[^)]*\)", text)
    assert outbox_calls, "no /outbox fetch found in chat UI"
    for call in outbox_calls:
        assert "after=" in call, f"outbox call missing ?after= contract: {call}"
