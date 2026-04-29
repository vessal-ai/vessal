"""Compaction Skill — preset Skill of the compaction Cell. Holds main Cell's
db_path and writes layer-≥1 schema-v1 YAML summaries via its own sqlite3
connection. Not intended for use in user agents — Hull instantiates it
automatically as part of the compaction Cell's boot script (see
docs/architecture/cell/06-compaction.md §6)."""

from ._skill import CompactionSkill

__all__ = ["CompactionSkill"]
