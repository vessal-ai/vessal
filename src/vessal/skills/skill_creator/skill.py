"""skill.py — skill_creator Skill implementation."""
from __future__ import annotations

from pathlib import Path

from vessal.ark.shell.cli.scaffold import write_skill_scaffold
from vessal.skills._base import BaseSkill


class SkillCreator(BaseSkill):
    """Skill scaffold generator. Delegates to write_skill_scaffold (single source of truth shared with `vessal skill create`)."""

    name = "skill_creator"
    description = "create new skill scaffold"

    def __init__(self) -> None:
        super().__init__()
        print("skill_creator: create(name) — scaffold a new Skill")

    def signal_update(self) -> None:
        self.signal = {}

    def create(self, name: str) -> str:
        """Create a Skill scaffold under <project>/skills/<name>/."""
        target_dir = Path(__file__).resolve().parent.parent  # <project>/skills/
        base = target_dir / name
        if base.exists():
            return f"Creation failed: {name} already exists at {base}"
        write_skill_scaffold(base, name)
        return (
            f"Created {name} at {base}. "
            f"Edit {base}/skill.py and {base}/SKILL.md, "
            f"then skill_manager.load('{name}')"
        )
