"""CompactionSkill class — see docs/architecture/cell/06-compaction.md §6.3."""

from __future__ import annotations

from vessal.skills._base import BaseSkill


class CompactionSkill(BaseSkill):
    name = "compaction"
    description = "frame compactor"

    def __init__(self, main_db_path: str) -> None:
        super().__init__()
        self._main_db_path = main_db_path
        print(f"[CompactionSkill] bound to {main_db_path}", flush=True)
