"""test_chat — Chat Skill tests."""
import json
import threading
import time

import pytest
from vessal.skills._base import BaseSkill
from vessal.skills.chat.skill import Chat


# ── Basics ──


def test_chat_is_skillbase():
    assert issubclass(Chat, BaseSkill)


def test_chat_has_required_attrs():
    assert isinstance(Chat.name, str) and Chat.name
    assert isinstance(Chat.description, str) and Chat.description


# ── receive() ──


def test_receive_adds_to_inbox():
    h = Chat()
    h.receive("hello")
    assert len(h._inbox) == 1
    assert h._inbox[0]["content"] == "hello"


def test_receive_with_sender():
    h = Chat()
    h.receive("hello", sender="alice")
    assert h._inbox[0]["sender"] == "alice"


def test_receive_appends_to_chat_log():
    h = Chat()
    h.receive("hello", sender="alice")
    assert len(h._chat_log) == 1
    assert h._chat_log[0]["role"] == "user"
    assert h._chat_log[0]["content"] == "hello"


def test_receive_increments_unread():
    h = Chat()
    h.receive("a")
    h.receive("b")
    assert h._unread_count == 2


# ── read() ──


def test_read_returns_recent():
    h = Chat()
    for i in range(10):
        h.receive(f"msg{i}")
    msgs = h.read(3)
    assert len(msgs) == 3
    assert msgs[0]["content"] == "msg7"
    assert msgs[-1]["content"] == "msg9"


def test_read_clears_unread():
    h = Chat()
    h.receive("msg")
    assert h._unread_count == 1
    h.read()
    assert h._unread_count == 0


def test_read_default_n():
    h = Chat()
    for i in range(10):
        h.receive(f"msg{i}")
    msgs = h.read()
    assert len(msgs) == 5  # default n=5


def test_read_includes_both_roles():
    h = Chat()
    h.receive("question")
    h.reply("answer")
    msgs = h.read()
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "agent"


def test_read_zero_returns_empty():
    h = Chat()
    h.receive("msg")
    assert h.read(0) == []


def test_read_empty():
    h = Chat()
    assert h.read() == []


# ── reply() ──


def test_reply_adds_to_outbox():
    h = Chat()
    h.reply("answer")
    assert len(h._outbox) == 1
    assert h._outbox[0]["content"] == "answer"


def test_reply_appends_to_chat_log():
    h = Chat()
    h.reply("answer")
    assert len(h._chat_log) == 1
    assert h._chat_log[0]["role"] == "agent"


def test_reply_no_wait_returns_none():
    h = Chat()
    result = h.reply("hello")
    assert result is None


def test_reply_wait_returns_response():
    h = Chat()

    def simulate_reply():
        time.sleep(0.3)
        h.receive("yes")

    t = threading.Thread(target=simulate_reply)
    t.start()
    result = h.reply("continue?", wait=5)
    t.join()
    assert result == "yes"


def test_reply_wait_unblocks_on_receive():
    """reply(wait=N) should return immediately when a message arrives, not sleep until next 1s tick."""
    h = Chat()

    def simulate_reply():
        time.sleep(0.05)  # 50ms — well under 1s sleep granularity
        h.receive("fast")

    t = threading.Thread(target=simulate_reply)
    t.start()
    start = time.time()
    result = h.reply("waiting", wait=10)
    elapsed = time.time() - start
    t.join()
    assert result == "fast"
    assert elapsed < 0.5, f"reply() took {elapsed:.2f}s — should be near-instant, not waiting for sleep(1) tick"


def test_reply_wait_timeout_returns_none():
    h = Chat()
    result = h.reply("hello?", wait=1)
    assert result is None


# ── drain_outbox() ──


def test_drain_outbox():
    h = Chat()
    h.reply("r1")
    h.reply("r2")
    msgs = h.drain_outbox()
    assert len(msgs) == 2
    assert h._outbox == []


# ── signal ──


def test_signal_empty_when_no_messages():
    h = Chat()
    h.signal_update()
    assert h.signal == {}


def test_signal_shows_unread_count():
    h = Chat()
    h.receive("a")
    h.receive("b")
    h.signal_update()
    assert h.signal != {}
    body = h.signal["recent"]
    assert "2 unread" in body
    assert "Must process unread messages" in body


def test_signal_shows_recent_messages():
    h = Chat()
    h.receive("question", sender="alice")
    h.read()  # clear unread
    h.reply("answer")
    h.signal_update()
    assert h.signal != {}
    body = h.signal["recent"]
    assert "alice" in body
    assert "question" in body
    assert "answer" in body


def test_signal_after_read_no_unread():
    h = Chat()
    h.receive("msg")
    h.read()
    h.signal_update()
    assert h.signal != {}
    body = h.signal["recent"]
    assert "unread" not in body
    assert "msg" in body


def test_signal_always_shows_history_even_with_unread():
    """Shows recent conversation even when there are unread messages."""
    h = Chat()
    h.receive("old msg")
    h.read()
    h.reply("old reply")
    h.receive("new msg")
    h.signal_update()
    assert h.signal != {}
    body = h.signal["recent"]
    assert "1 unread" in body
    assert "old msg" in body
    assert "new msg" in body


# ── Persistence ──


def test_no_persistence_without_ns():
    h = Chat()
    assert h._data_dir is None


def test_persistence_derives_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VESSAL_DATA_DIR", str(tmp_path))
    h = Chat()
    assert h._data_dir == tmp_path / "chat"
    assert h._data_dir.exists()


def test_persistence_saves_on_receive(tmp_path, monkeypatch):
    monkeypatch.setenv("VESSAL_DATA_DIR", str(tmp_path))
    h = Chat()
    h.receive("hello")
    chat_file = tmp_path / "chat" / "chat.jsonl"
    lines = [l for l in chat_file.read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["content"] == "hello"


def test_persistence_saves_on_reply(tmp_path, monkeypatch):
    monkeypatch.setenv("VESSAL_DATA_DIR", str(tmp_path))
    h = Chat()
    h.reply("answer")
    chat_file = tmp_path / "chat" / "chat.jsonl"
    lines = [l for l in chat_file.read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["role"] == "agent"


def test_persistence_loads_history_on_init(tmp_path, monkeypatch):
    monkeypatch.setenv("VESSAL_DATA_DIR", str(tmp_path))
    h1 = Chat()
    h1.receive("msg1")
    h1.reply("reply1")
    h2 = Chat()
    assert len(h2._chat_log) == 2
    assert h2._inbox == []  # inbox is not restored
    assert h2._unread_count == 0


def test_persistence_corrupted_file(tmp_path, monkeypatch):
    data_dir = tmp_path / "chat"
    data_dir.mkdir(parents=True)
    chat_file = data_dir / "chat.jsonl"
    good = {"ts": 1000.0, "role": "user", "content": "ok", "sender": "user"}
    chat_file.write_text(json.dumps(good) + "\nNOT JSON{{{\n", encoding="utf-8")
    monkeypatch.setenv("VESSAL_DATA_DIR", str(tmp_path))
    h = Chat()
    assert len(h._chat_log) == 1


# ── Integration ──


def test_chat_log_interleaved():
    h = Chat()
    h.receive("q1")
    h.reply("a1")
    h.receive("q2")
    h.reply("a2")
    roles = [e["role"] for e in h._chat_log]
    assert roles == ["user", "agent", "user", "agent"]


def test_old_tests_still_work_without_ns():
    h = Chat()
    h.receive("test")
    h.reply("ok")
    assert len(h._chat_log) == 2
    assert len(h._inbox) == 0  # reply() cleared inbox
    assert len(h._outbox) == 1


def test_read_clears_inbox():
    """_inbox should be empty after read()."""
    h = Chat()
    h.receive("msg1")
    h.receive("msg2")
    h.read()
    assert h._inbox == []


def test_reply_wait_ignores_already_read_messages():
    """reply(wait) should not return messages that were cleared by read()."""
    h = Chat()
    h.receive("old message")
    h.read()  # clear
    # reply(wait=1) should not find the old message
    result = h.reply("question?", wait=1)
    assert result is None


def test_reply_clears_unread():
    """_unread_count should be 0 after reply()."""
    h = Chat()
    h.receive("msg1")
    h.receive("msg2")
    assert h._unread_count == 2
    h.reply("answer")
    assert h._unread_count == 0
    assert h._inbox == []


def test_reply_clears_signal_pending():
    """signal should not contain [pending] after reply()."""
    h = Chat()
    h.receive("msg")
    h.reply("answer")
    h.signal_update()
    assert h.signal != {}
    body = h.signal["recent"]
    assert "pending" not in body
    assert "answer" in body
