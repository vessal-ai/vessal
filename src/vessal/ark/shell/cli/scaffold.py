"""scaffold.py — Skill scaffold writer for the Vessal CLI."""
from __future__ import annotations

from pathlib import Path

_DEFAULT_DESCRIPTION = "(functional description, ≤15 words)"


def write_skill_scaffold(base: Path, skill_name: str, description: str = _DEFAULT_DESCRIPTION) -> None:
    """Write a Skill scaffold into `base` with Python identifier `skill_name`.

    Creates: __init__.py, skill.py, SKILL.md, requirements.txt, tests/__init__.py,
    tests/test_{skill_name}.py. Shared between the `vessal skill init` CLI and the
    `skill_creator` Skill.
    """
    class_name = "".join(part.capitalize() for part in skill_name.split("_"))
    (base / "tests").mkdir(parents=True, exist_ok=True)

    (base / "__init__.py").write_text(
        f'"""{skill_name} — {description}"""\n'
        f'from .skill import {class_name} as Skill\n\n'
        f'__all__ = ["Skill"]\n',
        encoding="utf-8",
    )
    (base / "skill.py").write_text(
        f'"""skill.py — {skill_name} Skill implementation."""\n'
        f'from __future__ import annotations\n'
        f'\n'
        f'from vessal.ark.shell.hull.skill import SkillBase\n'
        f'\n'
        f'\n'
        f'class {class_name}(SkillBase):\n'
        f'    name = "{skill_name}"\n'
        f'    description = "{description}"\n'
        f'\n'
        f'    # ── Protocol conventions ──\n'
        f'    # 1. description ≤15 words, describe function not method names\n'
        f'    # 2. _signal() only shows state, does not expose method signatures\n'
        f'    # 3. SKILL.md is the only place containing method signatures\n'
        f'    # 4. _prompt() only contains behavior rules, not the API\n'
        f'\n'
        f'    def __init__(self):\n'
        f'        super().__init__()\n'
        f'        # Protect internal state with _ prefix to prevent Agent from bypassing the API\n'
        f'        # self._cache = {{}}\n'
        f'\n'
        f'    # Public methods: callable by Agent. Must produce observable feedback (print/return value/namespace diff)\n'
        f'    # def my_function(self, arg: str) -> str:\n'
        f'    #     """Tool description."""\n'
        f'    #     return arg\n'
        f'\n'
        f'    # Signal (optional, called each frame, returns (title, body) tuple)\n'
        f'    # def _signal(self) -> tuple[str, str] | None:\n'
        f'    #     return ("{skill_name}", "status info, no method names")\n',
        encoding="utf-8",
    )
    (base / "SKILL.md").write_text(
        # frontmatter for skills.list() discovery; body is the guide attribute (Agent reads via print(name.guide))
        f'---\n'
        f'name: {skill_name}\n'
        f'version: "0.1.0"\n'
        f'description: "{description}"\n'
        f'author: ""\n'
        f'license: "Apache-2.0"\n'
        f'requires:\n'
        f'  skills: []\n'
        f'---\n'
        f'\n'
        f'# {skill_name}\n'
        f'\n'
        f'(Operation manual. Agent reads via print({skill_name}.guide).\n'
        f'Contains method signatures and usage examples; keep concise.)\n'
        f'\n'
        f'## Methods\n'
        f'\n'
        f'(List method signatures.)\n',
        encoding="utf-8",
    )
    (base / "requirements.txt").write_text("", encoding="utf-8")
    (base / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (base / "tests" / f"test_{skill_name}.py").write_text(
        f'"""test_{skill_name} — {skill_name} Skill basic tests"""\n\n\n'
        f'def test_{skill_name}_placeholder():\n'
        f'    """Placeholder test; replace with real tests."""\n'
        f'    pass\n',
        encoding="utf-8",
    )
