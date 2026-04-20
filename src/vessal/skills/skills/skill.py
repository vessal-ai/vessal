"""skills — UI-only Skill exposing a management view for installed Skills."""
from __future__ import annotations

from vessal.ark.shell.hull.skill import SkillBase


class Skills(SkillBase):
    """Inventory and management UI for installed Skills. UI-only; no agent tools."""

    name = "skills"
    description = "skill inventory"
