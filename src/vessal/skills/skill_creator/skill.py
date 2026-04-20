"""skill.py — skill_creator Skill implementation."""
from __future__ import annotations

from pathlib import Path

from vessal.ark.shell.cli.scaffold import write_skill_scaffold
from vessal.ark.shell.hull.skill import SkillBase


class SkillCreator(SkillBase):
    """Skill scaffold generator. Delegates to the same scaffolder used by `vessal skill init` so the two
    surfaces cannot drift (single source of truth: ark.shell.cli.write_skill_scaffold).

    Attributes:
        _skill_paths: List of user Skill search paths.
    """

    name = "skill_creator"
    description = "create new skill scaffold"

    def __init__(self, ns: dict | None = None):
        super().__init__()
        self._skill_paths: list[str] = []
        if ns is not None:
            self._skill_paths = ns.get("skill_paths", [])

    def create(self, name: str, description: str) -> str:
        """Create a Skill scaffold under `skill_paths[0]`.

        The scaffold is identical to what `vessal skill init <name>` produces; `description` is
        written into the generated skill.py/SKILL.md so Agent does not need to edit them manually.

        Args:
            name: Skill name (snake_case).
            description: One-line function description (≤15 words, no method names).

        Returns:
            Operation result string.
        """
        if not self._skill_paths:
            return "Creation failed: skill_paths is empty, cannot determine target directory"

        base = Path(self._skill_paths[0]) / name
        if base.exists():
            return f"Creation failed: {name} already exists at {base}"

        write_skill_scaffold(base, name, description)
        return f"Created {name} at {base}. Edit skill.py to implement, then skills.load('{name}')"
