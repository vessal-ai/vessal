"""events.py — Shell-level event bus for SSE /events endpoint.

Thread-safe pub/sub. Each subscriber owns a bounded queue; publish is O(N subscribers)
but non-blocking (drops oldest when queue is full to avoid slow consumers blocking
the producer).
"""
from __future__ import annotations

import queue
import threading
from collections.abc import Iterator

_QUEUE_MAXSIZE = 256


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[queue.Queue[dict]] = []
        self._lock = threading.Lock()

    def publish(self, event: dict) -> None:
        with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                try:
                    q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    q.put_nowait(event)
                except queue.Full:
                    pass

    def open_queue(self) -> queue.Queue[dict]:
        """Register a subscription queue before sending HTTP headers.

        Caller must close it via close_queue() in a finally block.
        Use this when subscription must be registered before the HTTP response
        is flushed (avoids a race condition with SSE consumers).
        """
        q: queue.Queue[dict] = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        with self._lock:
            self._subscribers.append(q)
        return q

    def close_queue(self, q: queue.Queue[dict]) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def drain_queue(self, q: queue.Queue[dict], stop: threading.Event) -> Iterator[dict]:
        while not stop.is_set():
            try:
                ev = q.get(timeout=0.25)
            except queue.Empty:
                continue
            yield ev

    def subscribe(self, stop: threading.Event) -> Iterator[dict]:
        q = self.open_queue()
        try:
            yield from self.drain_queue(q, stop)
        finally:
            self.close_queue(q)
