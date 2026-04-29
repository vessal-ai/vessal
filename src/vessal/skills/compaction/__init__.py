"""Compaction Skill — preset Skill of the compaction Cell.

See docs/architecture/cell/06-compaction.md §6 for full design context.
"""

from importlib.resources import files

from ._skill import CompactionSkill

COMPACTION_SYSTEM_PROMPT: str = (
    files(__package__).joinpath("system.md").read_text(encoding="utf-8")
)

__all__ = ["CompactionSkill", "COMPACTION_SYSTEM_PROMPT"]
