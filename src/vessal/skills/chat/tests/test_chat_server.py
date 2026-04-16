import json
import threading
import time as time_mod
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from vessal.skills.chat.server import create_server


@pytest.fixture
def server_and_url(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    srv = create_server(data_dir, host="127.0.0.1", port=0)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv, f"http://127.0.0.1:{port}"
    srv.shutdown()


def post_json(url, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_json(url):
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def write_entry(data_dir, role, content, ts=None, **kwargs):
    if ts is None:
        ts = time_mod.time()
    entry = {"ts": ts, "role": role, "content": content, **kwargs}
    with open(data_dir / "chat.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def test_health(server_and_url):
    _, base = server_and_url
    result = get_json(f"{base}/health")
    assert result == {"status": "ok"}


def test_send_appends_to_chat_jsonl(server_and_url):
    srv, base = server_and_url
    result = post_json(f"{base}/inbox", {"content": "hello", "sender": "alice"})
    assert result["status"] == "ok"
    chat_file = srv.data_dir / "chat.jsonl"
    assert chat_file.exists()
    lines = [l for l in chat_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["content"] == "hello"
    assert entry["sender"] == "alice"
    assert entry["role"] == "user"


def test_send_default_sender(server_and_url):
    srv, base = server_and_url
    post_json(f"{base}/inbox", {"content": "hi"})
    chat_file = srv.data_dir / "chat.jsonl"
    lines = [l for l in chat_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    entry = json.loads(lines[0])
    assert entry["sender"] == "user"


def test_replies_empty(server_and_url):
    _, base = server_and_url
    result = get_json(f"{base}/outbox")
    assert result["messages"] == []


def test_replies_returns_agent_entries(server_and_url):
    srv, base = server_and_url
    ts = time_mod.time()
    write_entry(srv.data_dir, "agent", "done", ts=ts, recipient="user")
    result = get_json(f"{base}/outbox")
    assert len(result["messages"]) == 1
    assert result["messages"][0]["content"] == "done"
    # File should still exist after GET (append-only, no deletion)
    assert (srv.data_dir / "chat.jsonl").exists()


def test_replies_after_param(server_and_url):
    srv, base = server_and_url
    ts1 = 1000.0
    ts2 = 2000.0
    write_entry(srv.data_dir, "agent", "first", ts=ts1)
    write_entry(srv.data_dir, "agent", "second", ts=ts2)
    # Only entries after ts1 should be returned
    result = get_json(f"{base}/outbox?after={ts1}")
    assert len(result["messages"]) == 1
    assert result["messages"][0]["content"] == "second"


def test_replies_skips_user_entries(server_and_url):
    srv, base = server_and_url
    write_entry(srv.data_dir, "user", "user message", sender="alice")
    result = get_json(f"{base}/outbox")
    assert result["messages"] == []


def test_unknown_get_returns_404(server_and_url):
    _, base = server_and_url
    req = urllib.request.Request(f"{base}/unknown", method="GET")
    try:
        urllib.request.urlopen(req)
        assert False, "expected 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_unknown_post_returns_404(server_and_url):
    _, base = server_and_url
    body = b"{}"
    req = urllib.request.Request(
        f"{base}/unknown",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
        assert False, "expected 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404
