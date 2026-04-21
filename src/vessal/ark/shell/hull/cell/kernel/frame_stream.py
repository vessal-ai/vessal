"""frame_stream.py — Hierarchical frame stream.

Owns three zones:
  hot:              list of k-sized buckets B_0..B_4 (raw FrameRecord dicts)
  compression_zone: stripped bucket currently being compacted (or None)
  cold:             list of layers L_0..L_n (each a list of CompactionRecord dicts)

Plus bookkeeping:
  _in_flight:            True while a compaction LLM call is outstanding
  pending_compactions:   FIFO deque of layer indices awaiting compaction
  frames_since_snapshot: counter for periodic snapshot fallback (see Hull)

Thread safety: this class is NOT thread-safe. Only the main frame loop writes.
The compression worker thread produces CompactionRecord via a result queue;
the main loop drains and calls apply_results() atomically.
"""
from __future__ import annotations

from collections import deque
from typing import Any

from vessal.ark.shell.hull.cell.protocol import FRAME_SCHEMA_VERSION
from vessal.ark.shell.hull.cell.kernel.render._strip import strip_frame


class FrameStream:
    def __init__(self, k: int = 16, n: int = 8) -> None:
        if k < 1:
            raise ValueError(f"k must be >= 1, got {k}")
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n}")
        self._k = k
        self._n = n
        # Hot zone: list of 5 buckets. Index 0 = B_0 (freshest). Each bucket is a list of frame dicts.
        self._hot: list[list[dict]] = [[], [], [], [], []]
        self._compression_zone: list[dict] | None = None
        # Cold zone: list of layers. Lazily grown up to n entries.
        self._cold: list[list[dict]] = []
        self._in_flight: bool = False
        self._pending: deque[int] = deque()

    @property
    def k(self) -> int:
        return self._k

    @property
    def n(self) -> int:
        return self._n

    @property
    def in_flight(self) -> bool:
        return self._in_flight

    @property
    def compression_zone(self) -> list[dict] | None:
        return self._compression_zone

    def hot_frame_count(self) -> int:
        return sum(len(b) for b in self._hot)

    def cold_record_count(self) -> int:
        return sum(len(layer) for layer in self._cold)

    def latest_hot_frame(self) -> dict | None:
        """Most recently committed hot-zone frame, or None if the stream is empty."""
        return self._hot[0][-1] if self._hot[0] else None

    def hot_head_len(self) -> int:
        """Current length of the B_0 bucket (newest hot bucket)."""
        return len(self._hot[0])

    def find_creation(self, key: str) -> str | None:
        """Search hot buckets newest-first for the operation that first introduced `key`.

        Args:
            key: Variable name to search for in frame observation diffs.

        Returns:
            The operation string from the matching frame, or None if not found.
        """
        for bucket in self._hot:
            for frame in reversed(bucket):
                diff = frame.get("observation", {}).get("diff", "")
                if f"+ {key}" in diff:
                    return frame.get("pong", {}).get("action", {}).get("operation")
        return None

    def commit_frame(self, frame: dict) -> None:
        """Append a raw frame dict to B_0. Called by Kernel._commit_frame."""
        if frame.get("schema_version") != FRAME_SCHEMA_VERSION:
            raise ValueError(
                f"FrameStream.commit_frame: schema_version mismatch, "
                f"got {frame.get('schema_version')}, expected {FRAME_SCHEMA_VERSION}"
            )
        self._hot[0].append(frame)

    def try_shift(self) -> dict | None:
        """Evaluate the three-term shift predicate. Returns a compaction task dict or None.

        Task dict shape: {"layer": int, "payload": list[dict]}
          layer=0 means compacting a stripped hot bucket into L_0.
          layer>0 means compacting the oldest k records of L_{layer-1} into L_{layer}.

        Sets self._in_flight = True on success. Caller must eventually call
        apply_results() with the resulting record (or clear state on failure).
        """
        if self._in_flight:
            return None

        if self._pending:
            layer = self._pending.popleft()
            payload = self._extract_payload_for_layer(layer)
            self._in_flight = True
            return {"layer": layer, "payload": payload}

        # Hot-shift predicate: len(B_0) >= k ∧ compression_zone empty ∧ no in-flight
        if len(self._hot[0]) < self._k:
            return None
        if self._compression_zone is not None:
            return None
        return self._do_hot_shift()

    def _extract_payload_for_layer(self, layer: int) -> list[dict]:
        """Pop the oldest k records of L_{layer-1} for merging into L_{layer}.

        Semantics: "L_i fills to k, a new one triggers compaction, result goes to L_{i+1},
        L_i drops back to 1." We take the oldest k out; the most-recent residual stays.
        """
        src = layer - 1
        if src < 0 or src >= len(self._cold):
            return []
        bucket = self._cold[src]
        if len(bucket) < self._k:
            return []
        payload = bucket[: self._k]
        self._cold[src] = bucket[self._k :]
        return payload

    def _do_hot_shift(self) -> dict:
        """Shift hot buckets one slot; strip old B_4 to level 4 into compression_zone.

        Returns compaction task for layer 0. Sets in_flight.
        """
        # old B_4 becomes compression payload (stripped to level 4)
        ejected = self._hot[4]
        raw_bytes = sum(len(str(f)) for f in ejected)
        stripped = [strip_frame(f, 4) for f in ejected]
        stripped_bytes = sum(len(str(f)) for f in stripped)
        self._compression_zone = stripped
        # Cascade: B_3→B_4, B_2→B_3, B_1→B_2, B_0→B_1, new B_0 empty
        self._hot = [[], self._hot[0], self._hot[1], self._hot[2], self._hot[3]]
        self._in_flight = True
        return {"layer": 0, "payload": list(stripped), "raw_bytes": raw_bytes, "stripped_bytes": stripped_bytes}

    def apply_results(self, results: list[tuple[dict, int]]) -> None:
        """Append compacted records to cold zone; enqueue cascades if any L_i overflows.

        Cascade rule: "L_i fills to k, new one triggers compaction, result goes to L_{i+1},
        L_i drops back to 1." Trigger fires at len > k (i.e. k+1).

        Args:
            results: list of (CompactionRecord-as-dict, target_layer) tuples.
        """
        for record, target_layer in results:
            while len(self._cold) <= target_layer:
                if len(self._cold) >= self._n:
                    if self._cold and self._cold[-1]:
                        self._cold[-1].pop(0)
                    break
                self._cold.append([])
            if target_layer < len(self._cold):
                self._cold[target_layer].append(record)
                if len(self._cold[target_layer]) > self._k and target_layer + 1 < self._n:
                    self._pending.append(target_layer + 1)
        self._compression_zone = None
        self._in_flight = False

    def abort_compaction(self) -> None:
        """Clear compression_zone + reset _in_flight without appending any record.

        Called when the worker returns a 'skip' (empty payload) or 'error' sentinel.
        """
        self._compression_zone = None
        self._in_flight = False

    def to_dict(self) -> dict:
        return {
            "schema_version": FRAME_SCHEMA_VERSION,
            "k": self._k,
            "n": self._n,
            "hot": [list(b) for b in self._hot],
            "compression_zone": (
                list(self._compression_zone) if self._compression_zone is not None else None
            ),
            "cold": [list(layer) for layer in self._cold],
            "in_flight": self._in_flight,
            "pending": list(self._pending),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FrameStream":
        if d.get("schema_version") != FRAME_SCHEMA_VERSION:
            raise ValueError(
                f"FrameStream.from_dict: schema_version mismatch, "
                f"got {d.get('schema_version')}, expected {FRAME_SCHEMA_VERSION}"
            )
        fs = cls(k=d["k"], n=d["n"])
        fs._hot = [list(b) for b in d["hot"]]
        fs._compression_zone = (
            list(d["compression_zone"]) if d["compression_zone"] is not None else None
        )
        fs._cold = [list(layer) for layer in d["cold"]]
        fs._in_flight = bool(d["in_flight"])
        fs._pending = deque(d["pending"])
        return fs

    def project_render(self) -> dict:
        """View for renderer: cold older-first (L_n..L_0), hot older-first (B_4..B_0).

        Each hot bucket is pre-stripped by its level (B_0 raw, B_4 strip level 4).
        """
        cold_view: list[list[dict]] = []
        for layer in reversed(self._cold):
            cold_view.append(list(layer))
        hot_view: list[list[dict]] = []
        for i in reversed(range(5)):
            bucket = self._hot[i]
            hot_view.append([strip_frame(f, i) for f in bucket])
        return {"cold": cold_view, "hot": hot_view}

    def project_compactions(self) -> dict:
        """View for the /state/compactions endpoint."""
        return {
            "schema_version": FRAME_SCHEMA_VERSION,
            "k": self._k,
            "n": self._n,
            "in_flight": self._in_flight,
            "pending": list(self._pending),
            "layers": [
                {"layer": idx, "records": [dict(r) for r in layer]}
                for idx, layer in enumerate(self._cold)
            ],
        }

    def stats(self) -> dict:
        """Lightweight state for observability; safe to emit every frame."""
        return {
            "hot_counts": [len(b) for b in self._hot],
            "cold_counts": [len(layer) for layer in self._cold],
            "in_flight": self._in_flight,
            "pending_depth": len(self._pending),
        }
