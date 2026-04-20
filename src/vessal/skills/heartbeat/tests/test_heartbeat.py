"""test_heartbeat — Heartbeat Skill and server tests."""
from __future__ import annotations

import threading
import time

import pytest

from vessal.skills.heartbeat import server as heartbeat_server
from vessal.skills.heartbeat.server import _HeartbeatServer
from vessal.skills.heartbeat.skill import Skill


class _FakeHullApi:
    def __init__(self):
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def wake(self, reason: str = "skill") -> None:
        with self._lock:
            self.calls.append(reason)


@pytest.fixture(autouse=True)
def _reset_module_instance():
    yield
    if heartbeat_server._instance is not None:
        heartbeat_server.stop()


def test_skill_is_skillbase_subclass():
    from vessal.ark.shell.hull.skill import SkillBase
    assert issubclass(Skill, SkillBase)


def test_skill_attributes():
    assert Skill.name == "heartbeat"
    assert isinstance(Skill.description, str) and Skill.description
    assert isinstance(Skill.guide, str) and Skill.guide


def test_instance_start_launches_thread():
    api = _FakeHullApi()
    srv = _HeartbeatServer(api, interval=10.0)
    srv.start()
    try:
        assert srv._thread.is_alive()
    finally:
        srv.stop()
    assert not srv._thread.is_alive()


def test_instance_wakes_at_interval():
    api = _FakeHullApi()
    srv = _HeartbeatServer(api, interval=0.05)
    srv.start()
    try:
        time.sleep(0.18)
    finally:
        srv.stop()
    assert "heartbeat" in api.calls
    assert len(api.calls) >= 2


def test_instance_stop_before_any_wake_is_clean():
    api = _FakeHullApi()
    srv = _HeartbeatServer(api, interval=10.0)
    srv.start()
    srv.stop()
    assert api.calls == []
    assert not srv._thread.is_alive()


def test_module_start_creates_instance():
    api = _FakeHullApi()
    heartbeat_server.start(api, heartbeat=10.0)
    assert heartbeat_server._instance is not None
    assert heartbeat_server._instance._thread.is_alive()


def test_module_stop_clears_instance():
    api = _FakeHullApi()
    heartbeat_server.start(api, heartbeat=10.0)
    heartbeat_server.stop()
    assert heartbeat_server._instance is None


def test_module_stop_noop_when_not_started():
    heartbeat_server.stop()
    assert heartbeat_server._instance is None


def test_module_start_twice_replaces_previous_instance():
    api1 = _FakeHullApi()
    heartbeat_server.start(api1, heartbeat=10.0)
    first = heartbeat_server._instance

    api2 = _FakeHullApi()
    heartbeat_server.start(api2, heartbeat=10.0)
    second = heartbeat_server._instance

    assert second is not first
    assert not first._thread.is_alive()
    assert second._thread.is_alive()


def test_module_default_heartbeat_is_1800_seconds():
    api = _FakeHullApi()
    heartbeat_server.start(api)
    try:
        assert heartbeat_server._instance._interval == 1800.0
    finally:
        heartbeat_server.stop()
