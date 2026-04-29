"""CompactionSkill class — see docs/architecture/cell/06-compaction.md §6.3."""

from __future__ import annotations

import sqlite3

from vessal.skills._base import BaseSkill


class CompactionSkill(BaseSkill):
    name = "compaction"
    description = "frame compactor"

    def __init__(self, main_db_path: str) -> None:
        super().__init__()
        self._main_db_path = main_db_path
        print(f"[CompactionSkill] bound to {main_db_path}", flush=True)

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
