"""test_shell_scheduler — heartbeat skill server timer tests.

Heartbeat scheduling has been migrated from ShellServer to vessal.skills.heartbeat.server.
"""
import time
from unittest.mock import MagicMock

import pytest

from vessal.skills.heartbeat import server as heartbeat_server


@pytest.fixture(autouse=True)
def reset_heartbeat_instance():
    """Reset the heartbeat server global instance before and after each test to ensure isolation."""
    heartbeat_server.stop()
    yield
    heartbeat_server.stop()


class TestHeartbeatSkillServer:
    """heartbeat skill server owns the heartbeat timer."""

    def test_heartbeat_calls_hull_api_wake(self):
        """When heartbeat fires, heartbeat server calls hull_api.wake('heartbeat')."""
        hull_api = MagicMock()
        heartbeat_server.start(hull_api, heartbeat=0.1)
        time.sleep(0.3)
        heartbeat_server.stop()
        hull_api.wake.assert_any_call("heartbeat")

    def test_stop_prevents_further_wakes(self):
        """No more heartbeats fire after stop()."""
        hull_api = MagicMock()
        heartbeat_server.start(hull_api, heartbeat=0.1)
        time.sleep(0.15)
        heartbeat_server.stop()
        call_count = hull_api.wake.call_count
        # wait one heartbeat period after stop; call_count should not increase
        time.sleep(0.2)
        assert hull_api.wake.call_count == call_count

    def test_shell_server_is_pure_http(self):
        """ShellServer no longer has _scheduler_thread or heartbeat parameter."""
        from vessal.ark.shell.server import ShellServer
        import inspect
        sig = inspect.signature(ShellServer.__init__)
        assert "heartbeat" not in sig.parameters
        assert "_scheduler_thread" not in ShellServer.__dict__
