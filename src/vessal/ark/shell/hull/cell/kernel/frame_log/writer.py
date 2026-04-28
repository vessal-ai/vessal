"""writer.py — FrameLog: transactional 5-table writer.

Write order per kernel/04-frame-log.md §4.6:
  BEGIN
    INSERT errors (if any)
    INSERT frame_content (full row, refs errors via *_error_id)
    INSERT signals (if any)
    INSERT entries  ← LAST: row's existence = "frame complete"
  COMMIT
"""
from __future__ import annotations

import sqlite3

from .types import ErrorOnSource, FrameWriteSpec, SignalRow


class FrameLog:
    """Transactional writer for the 5-table frame_log SQLite schema.

    Attributes:
        conn: open sqlite3.Connection (caller owns lifecycle).
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def write_frame(self, spec: FrameWriteSpec) -> None:
        """Persist one layer=0 frame in a single transaction.

        Args:
            spec: FrameWriteSpec with all fields populated.
        """
        cur = self.conn.cursor()
        cur.execute("BEGIN")
        try:
            obs_error_id = self._maybe_insert_error(cur, spec.n, spec.operation_error)
            verdict_error_id = self._maybe_insert_error(cur, spec.n, spec.verdict_error)
            cur.execute(
                "INSERT INTO frame_content("
                "n, pong_think, pong_operation, pong_expect, "
                "obs_stdout, obs_stderr, obs_diff_json, obs_error_id, "
                "verdict_value, verdict_error_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    spec.n,
                    spec.pong_think,
                    spec.pong_operation,
                    spec.pong_expect,
                    spec.obs_stdout,
                    spec.obs_stderr,
                    spec.obs_diff_json,
                    obs_error_id,
                    spec.verdict_value,
                    verdict_error_id,
                ),
            )
            for sig in spec.signals:
                self._insert_signal(cur, spec.n, sig)
            cur.execute(
                "INSERT INTO entries(layer, n_start, n_end) VALUES (0, ?, ?)",
                (spec.n, spec.n),
            )
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise

    def _maybe_insert_error(
        self, cur: sqlite3.Cursor, n: int, err: ErrorOnSource | None
    ) -> int | None:
        if err is None:
            return None
        cur.execute(
            "INSERT INTO errors(layer, n_start, source, source_detail, format_text) "
            "VALUES (0, ?, ?, ?, ?)",
            (n, err.source, err.source_detail, err.format_text),
        )
        return cur.lastrowid

    def _insert_signal(self, cur: sqlite3.Cursor, n: int, sig: SignalRow) -> None:
        if (sig.payload_json is None) == (sig.error is None):
            raise ValueError(
                "SignalRow must set exactly one of payload_json or error "
                f"(got payload={sig.payload_json!r}, error={sig.error!r})"
            )
        error_id: int | None = None
        if sig.error is not None:
            cur.execute(
                "INSERT INTO errors(layer, n_start, source, source_detail, format_text) "
                "VALUES (0, ?, 'signal_update', ?, ?)",
                (n, sig.error.source_detail, sig.error.format_text),
            )
            error_id = cur.lastrowid
        cur.execute(
            "INSERT INTO signals(n_start, class_name, var_name, scope, payload_json, error_id) "
            "VALUES (?,?,?,?,?,?)",
            (n, sig.class_name, sig.var_name, sig.scope, sig.payload_json, error_id),
        )

    def last_committed_frame(self) -> int | None:
        """Return MAX(n_start) over layer=0 entries, or None if empty.

        On boot, the next frame number is `(last_committed_frame() or 0) + 1`.
        """
        row = self.conn.execute(
            "SELECT MAX(n_start) FROM entries WHERE layer = 0"
        ).fetchone()
        return None if row is None or row[0] is None else int(row[0])

    def cleanup_partial(self) -> int:
        """DELETE frame_content rows whose n exceeds the last committed frame.

        These are orphans from a process that crashed between INSERT frame_content
        (Phase 1 in §4.6) and INSERT entries (Phase 4). Returns count of rows deleted.
        """
        last = self.last_committed_frame()
        threshold = -1 if last is None else last
        cur = self.conn.execute(
            "DELETE FROM frame_content WHERE n > ?", (threshold,)
        )
        return cur.rowcount
