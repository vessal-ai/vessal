"""test_core_composer_wiring.py — Core.step() flattens dataclass Ping via composer."""
from __future__ import annotations

from unittest.mock import patch

from vessal.ark.shell.hull.cell.protocol import (
    FrameStream, Ping, State,
)


def test_build_messages_returns_list():
    from vessal.ark.shell.hull.cell.core.core import Core
    ping = Ping(
        system_prompt="sys",
        state=State(frame_stream=FrameStream(entries=[]), signals={}),
    )
    msgs = Core._build_messages(ping)
    assert isinstance(msgs, list)
    assert len(msgs) >= 1
    assert msgs[0]["role"] == "system"


def test_build_messages_delegates_to_composer():
    """Core._build_messages calls composer.compose."""
    from vessal.ark.shell.hull.cell.core.core import Core
    ping = Ping(
        system_prompt="sys",
        state=State(frame_stream=FrameStream(entries=[]), signals={}),
    )
    with patch("vessal.ark.shell.hull.cell.core.composer.compose", wraps=lambda p: [{"role": "system", "content": p.system_prompt}]) as mock_compose:
        Core._build_messages(ping)
    mock_compose.assert_called_once_with(ping)
