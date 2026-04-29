"""Compaction Skill — preset Skill of the compaction Cell.

See docs/architecture/cell/06-compaction.md §6 for full design context.
"""

from vessal.ark.util.compaction_prompts import COMPACTION_SYSTEM_PROMPT

from ._skill import CompactionSkill

__all__ = ["CompactionSkill", "COMPACTION_SYSTEM_PROMPT"]
