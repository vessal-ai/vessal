"""chat Skill — bidirectional human communication.

Agent interface: read() fetches conversation history and clears unread; reply() sends a message and clears unread.
Shell interface: receive() delivers a message; drain_outbox() retrieves replies.
Persistence: all messages are written append-only to data/chat.jsonl.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path

from vessal.ark.shell.hull.skill import SkillBase


class Chat(SkillBase):
    """Bidirectional human communication Skill."""

    name = "chat"
    description = "send/receive messages"

    def __init__(self, ns=None):
        super().__init__()
        self._inbox: list[dict] = []
        self._outbox: list[dict] = []
        self._unread_count: int = 0
        self._chat_log: list[dict] = []
        self._data_dir: Path | None = None
        self._inbox_event = threading.Event()

        if ns is not None:
            base = ns.get("_data_dir")
            if base:
                self._data_dir = Path(base) / "chat"
                self._data_dir.mkdir(parents=True, exist_ok=True)
                self._load_chat()

    # ── Agent interface ──

    def read(self, n: int = 5) -> list[dict]:
        """Return the most recent n conversation entries (user + agent) and clear the unread marker.

        Args:
            n: Number of entries to return; default 5.

        Returns:
            Most recent n conversation entries, each containing role/content/ts fields.
        """
        self._unread_count = 0
        self._inbox.clear()
        if n <= 0:
            return []
        return list(self._chat_log[-n:])

    def reply(self, content: str, wait: int = 0) -> str | None:
        """Send a message to the human.

        Args:
            content: Message content.
            wait: Seconds to wait for a human reply. 0 = do not wait, return None immediately.

        Returns:
            When wait > 0: the human reply content, or None on timeout.
            When wait = 0: None.

        Note:
            Calling reply() clears the unread marker (_unread_count reset to zero, _inbox cleared),
            consistent with read() behavior. reply(wait=N) clears old messages first, then waits for new ones.
        """
        ts = time.time()
        self._outbox.append({
            "content": content,
            "recipient": "user",
            "timestamp": ts,
        })
        entry = {"ts": ts, "role": "agent", "content": content}
        self._chat_log.append(entry)
        self._append_entry(entry)
        # Replying is acknowledgement — clear unread state
        self._unread_count = 0
        self._inbox.clear()

        if wait <= 0:
            return None

        self._inbox_event.clear()
        deadline = time.time() + wait
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            self._inbox_event.wait(timeout=remaining)
            self._inbox_event.clear()
            if self._inbox:
                msg = self._inbox.pop(0)
                self._unread_count = len(self._inbox)
                return msg["content"]

    # ── Shell interface (not called by Agent) ──

    def receive(self, content: str, sender: str = "user") -> None:
        """Deliver a human message to the inbox and persist it to chat.jsonl."""
        ts = time.time()
        self._inbox.append({
            "content": content,
            "sender": sender,
            "timestamp": ts,
            "read": False,
        })
        self._unread_count += 1
        entry = {"ts": ts, "role": "user", "content": content, "sender": sender}
        self._chat_log.append(entry)
        self._append_entry(entry)
        self._inbox_event.set()

    def drain_outbox(self) -> list[dict]:
        """Retrieve all pending replies and clear the outbox."""
        msgs = list(self._outbox)
        self._outbox.clear()
        return msgs

    # ── Signal ──

    def _signal(self) -> tuple[str, str] | None:
        """Per-frame signal: unread count + most recent 5 conversation entries."""
        recent = self._chat_log[-5:]
        if not recent and self._unread_count == 0:
            return None

        lines = []
        if self._unread_count > 0:
            lines.append(
                f"[pending] Inbox has {self._unread_count} unread message(s)."
                f" Must process unread messages this frame. Check guide for instructions."
            )

        for entry in recent:
            ts = datetime.fromtimestamp(entry["ts"]).strftime("%H:%M")
            role = entry.get("sender", "agent") if entry["role"] == "user" else "agent"
            preview = entry["content"][:60]
            lines.append(f"  [{ts}] {role}: {preview}")

        return ("chat", "\n".join(lines))

    # ── Internal ──

    def _append_entry(self, entry: dict) -> None:
        """Append a JSONL entry to data/chat.jsonl."""
        if self._data_dir is None:
            return
        path = self._data_dir / "chat.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _load_chat(self) -> None:
        """Restore conversation history from data/chat.jsonl into _chat_log. Does not restore inbox."""
        if self._data_dir is None:
            return
        path = self._data_dir / "chat.jsonl"
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            self._chat_log.append(entry)
