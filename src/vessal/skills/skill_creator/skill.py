"""skill.py — skill_creator Skill implementation."""
from __future__ import annotations

from pathlib import Path

from vessal.ark.shell.cli.scaffold import write_skill_scaffold
from vessal.skills._base import BaseSkill


class SkillCreator(BaseSkill):
    """Skill scaffold generator. Delegates to the same scaffolder used by `vessal skill create` so the two
    surfaces cannot drift (single source of truth: ark.shell.cli.write_skill_scaffold).

    Attributes:
        _skill_paths: List of user Skill search paths.
    """

    name = "skill_creator"
    description = "create new skill scaffold"

    def __init__(self) -> None:
        super().__init__()
        self._skill_paths: list[str] = []
        print("skill_creator: create(name) — scaffold a new Skill")

    def create(self, name: str) -> str:
        """Create a Skill scaffold under `skill_paths[0]`.

        The scaffold is identical to what `vessal skill create` produces. The generated
        skill.py and SKILL.md carry a placeholder description; edit them after creation
        to fill in the real function description.

        Args:
            name: Skill name (snake_case).

        Returns:
            Operation result string.
        """
        if not self._skill_paths:
            return "Creation failed: skill_paths is empty, cannot determine target directory"

        base = Path(self._skill_paths[0]) / name
        if base.exists():
            return f"Creation failed: {name} already exists at {base}"

        write_skill_scaffold(base, name)
        return (
            f"Created {name} at {base}. "
            f"Edit {base}/skill.py and {base}/SKILL.md to fill in the description, "
            f"then skills.load('{name}')"
        )
