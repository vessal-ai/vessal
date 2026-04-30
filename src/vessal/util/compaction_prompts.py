"""Compaction Cell system prompts — loaded by Hull to initialize compaction Cell.

This module is in ark.util (not Skills) to maintain the architecture boundary:
Hull must never import Skills directly. The COMPACTION_SYSTEM_PROMPT is part of the
Cell initialization, which Hull owns.

See: R-Cell-2026-04-21 (Cell Boundary rule in CLAUDE.md)
"""

from pathlib import Path

_SYSTEM_PROMPT_PATH = (
    Path(__file__).parent.parent / "skills" / "compaction" / "system.md"
)

COMPACTION_SYSTEM_PROMPT: str = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

__all__ = ["COMPACTION_SYSTEM_PROMPT"]
