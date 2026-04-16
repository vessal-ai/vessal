"""UI Server route tests."""
import json
from unittest.mock import MagicMock

import pytest

from vessal.skills.ui.skill import UI
from vessal.skills.ui import server


@pytest.fixture
def ui_skill():
    return UI()


@pytest.fixture
def mock_hull_api():
    api = MagicMock()
    api.register_route = MagicMock()
    api.unregister_route = MagicMock()
    api.wake = MagicMock()
    return api


@pytest.fixture(autouse=True)
def server_lifecycle(mock_hull_api, ui_skill):
    """Ensure server is properly started and stopped for each test.

    Autouse ensures stop() always runs even if assertions fail mid-test,
    preventing module global state leakage between tests.
    """
    server.start(mock_hull_api, skill=ui_skill)
    yield
    server.stop()


class TestStartStop:
    def test_start_registers_routes(self, mock_hull_api, ui_skill):
        # At minimum: /, /render, /events
        route_calls = mock_hull_api.register_route.call_args_list
        paths = [call[0][1] for call in route_calls]
        assert "/" in paths
        assert "/render" in paths
        assert "/events" in paths

    def test_stop_unregisters(self, mock_hull_api, ui_skill):
        # Explicitly test that stop() calls unregister_route
        # (teardown will also call stop(), but that's for cleanup)
        initial_call_count = mock_hull_api.unregister_route.call_count
        server.stop()
        # stop() should have called unregister_route for /, /render, /events, and static files
        assert mock_hull_api.unregister_route.call_count > initial_call_count


class TestRenderRoute:
    def test_render_returns_empty_initially(self, mock_hull_api, ui_skill):
        status, resp = server._handle_render(None)
        assert status == 200
        assert resp["version"] == -1  # No render yet

    def test_render_returns_latest_after_skill_render(self, mock_hull_api, ui_skill):
        ui_skill.render([ui_skill.text("hello")])
        status, resp = server._handle_render(None)
        assert status == 200
        assert resp["version"] == 0
        assert len(resp["components"]) == 1

    def test_render_conditional_on_version(self, mock_hull_api, ui_skill):
        ui_skill.render([ui_skill.text("hello")])
        # Client already has version 0
        status, resp = server._handle_render({"after_version": 0})
        assert status == 200
        assert resp.get("unchanged", False) is True

    def test_render_empty_response_has_correct_structure(self, mock_hull_api, ui_skill):
        status, resp = server._handle_render(None)
        assert status == 200
        assert resp["version"] == -1
        assert "components" in resp  # Must have components key, not "unchanged"
        assert "unchanged" not in resp  # Must NOT return unchanged on first request


class TestEventsRoute:
    def test_post_event_to_inbox(self, mock_hull_api, ui_skill):
        event = {"event": "click", "id": "btn-1", "ts": 1.0}
        status, resp = server._handle_events(event)
        assert status == 200
        assert len(ui_skill._inbox) == 1
        assert ui_skill._inbox[0]["event"] == "click"

    def test_post_event_wakes_agent(self, mock_hull_api, ui_skill):
        server._handle_events({"event": "avatar_tap", "ts": 1.0})
        mock_hull_api.wake.assert_called_once()
