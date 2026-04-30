"""Compaction class — see docs/architecture/cell/06-compaction.md §6.3."""

from __future__ import annotations

import sqlite3

from vessal.skills._base import BaseSkill
from ._pending import (
    K,
    MAX_LAYER,
    PendingGroup,
    PendingView,
    fetch_uncovered_on_layer,
)

_FIELD_TRUNC = 500
_OPERATION_TRUNC = 1000


def _truncate(value: str | None, n: int) -> str:
    if value is None:
        return ""
    return value if len(value) <= n else value[:n] + "..."


class Compaction(BaseSkill):
    name = "compaction"
    description = "frame compactor"

    def __init__(self, main_db_path: str) -> None:
        super().__init__()
        self._main_db_path = main_db_path
        print(f"[Compaction] bound to {main_db_path}", flush=True)

    def write_summary(
        self,
        layer: int,
        n_start: int,
        n_end: int,
        schema_version: int,
        body: str,
    ) -> None:
        # Why isolation_level=None: required for explicit BEGIN/COMMIT control
        # because Python's sqlite3 default driver issues an implicit BEGIN before
        # every DML statement otherwise.
        conn = sqlite3.connect(self._main_db_path, isolation_level=None)
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            conn.execute("BEGIN")
            conn.execute(
                "INSERT INTO entries(layer, n_start, n_end) VALUES (?,?,?)",
                (layer, n_start, n_end),
            )
            conn.execute(
                "INSERT INTO summary_content(layer, n_start, schema_version, body) "
                "VALUES (?,?,?,?)",
                (layer, n_start, schema_version, body),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def read_pending(self) -> PendingView:
        """Snapshot of pending compaction work across all layers."""
        conn = sqlite3.connect(self._main_db_path)
        try:
            groups: list[PendingGroup] = []
            for layer in range(MAX_LAYER):
                uncovered = fetch_uncovered_on_layer(conn, layer)
                full_chunks = len(uncovered) // K
                if full_chunks == 0:
                    continue
                for i in range(full_chunks):
                    chunk = uncovered[i * K : (i + 1) * K]
                    items = [self._render_item(conn, layer, ns, ne) for (ns, ne) in chunk]
                    groups.append(PendingGroup(
                        layer=layer,
                        n_start=chunk[0][0],
                        n_end=chunk[-1][1],
                        items=items,
                    ))
            return PendingView(groups=groups)
        finally:
            conn.close()

    def _render_item(self, conn, source_layer, n_start, n_end):
        if source_layer == 0:
            return self._render_l0_item(conn, n_start)
        return self._render_l_ge_1_item(conn, source_layer, n_start)

    def _render_l0_item(self, conn, n) -> dict:
        row = conn.execute(
            "SELECT pong_think, pong_operation, pong_expect, obs_stdout, obs_stderr, "
            "       obs_error_id, verdict_value "
            "FROM frame_content WHERE n=?",
            (n,),
        ).fetchone()
        if row is None:
            return {"n": n, "missing": True}
        think, op, exp, stdout, stderr, error_id, verdict = row
        error_text = ""
        if error_id is not None:
            err = conn.execute("SELECT format_text FROM errors WHERE id=?", (error_id,)).fetchone()
            if err is not None:
                error_text = err[0]
        return {
            "n": n,
            "think": _truncate(think, _FIELD_TRUNC),
            "operation": _truncate(op, _OPERATION_TRUNC),
            "expect": _truncate(exp, _FIELD_TRUNC),
            "stdout": _truncate(stdout, _FIELD_TRUNC),
            "stderr": _truncate(stderr, _FIELD_TRUNC),
            "error": _truncate(error_text, _FIELD_TRUNC),
            "verdict": verdict,
        }

    def _render_l_ge_1_item(self, conn, layer, n_start) -> str:
        row = conn.execute(
            "SELECT body FROM summary_content WHERE layer=? AND n_start=?",
            (layer, n_start),
        ).fetchone()
        return row[0] if row is not None else ""
