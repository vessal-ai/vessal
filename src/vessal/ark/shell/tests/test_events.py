"""Tests for the Shell-level event bus."""
import json
import threading
import time

from vessal.ark.shell.events import EventBus


def test_subscribe_receives_published_event():
    bus = EventBus()
    received: list[dict] = []
    stop = threading.Event()

    def consumer():
        for ev in bus.subscribe(stop):
            received.append(ev)
            if len(received) >= 2:
                stop.set()

    t = threading.Thread(target=consumer, daemon=True)
    t.start()
    time.sleep(0.05)
    bus.publish({"type": "frame", "ts": 1.0, "payload": {"number": 1}})
    bus.publish({"type": "frame", "ts": 2.0, "payload": {"number": 2}})
    t.join(timeout=2.0)
    assert not t.is_alive()
    assert [e["payload"]["number"] for e in received] == [1, 2]


def test_multiple_subscribers_each_get_event():
    bus = EventBus()
    received_a: list[dict] = []
    received_b: list[dict] = []
    stop_a = threading.Event()
    stop_b = threading.Event()

    def consume(into, stop):
        for ev in bus.subscribe(stop):
            into.append(ev)
            stop.set()

    ta = threading.Thread(target=consume, args=(received_a, stop_a), daemon=True)
    tb = threading.Thread(target=consume, args=(received_b, stop_b), daemon=True)
    ta.start(); tb.start()
    time.sleep(0.05)
    bus.publish({"type": "agent_crash", "ts": 0.0, "payload": {"reason": "x"}})
    ta.join(1.0); tb.join(1.0)
    assert len(received_a) == 1 and len(received_b) == 1


def test_sse_endpoint_streams_events(tmp_path, monkeypatch):
    import urllib.request

    (tmp_path / "hull.toml").write_text("[agent]\nname = 'x'\n")
    from vessal.ark.shell.server import ShellServer

    server = ShellServer(project_dir=str(tmp_path), port=0)
    monkeypatch.setattr(server, "_spawn_hull", lambda: setattr(server, "_internal_port", 9999))
    monkeypatch.setattr(server, "_monitor_hull", lambda: None)
    server.start()
    try:
        url = f"http://127.0.0.1:{server.port}/events"
        resp = urllib.request.urlopen(url, timeout=2)

        server.event_bus.publish({"type": "frame", "ts": 0.0, "payload": {"number": 7}})
        line = resp.readline().decode()
        assert line.startswith("data: ")
        data = json.loads(line[len("data: "):])
        assert data["payload"]["number"] == 7
    finally:
        server.shutdown()
