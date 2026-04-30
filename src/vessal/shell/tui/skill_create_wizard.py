"""skill_create_wizard.py — interactive wizard invoked by `vessal skill create`."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SkillCreateChoices:
    name: str
    with_tutorial: bool
    with_ui: bool
    with_server: bool


def validate_skill_name(name: str) -> str | None:
    """Return an error message if `name` is not a valid Python identifier, else None."""
    if not name or not name.strip():
        return "Skill name cannot be empty."
    candidate = name.strip()
    if not candidate.isidentifier():
        return "Skill name must be a valid Python identifier (letters, digits, underscore; no leading digit)."
    return None


def run_skill_create_wizard() -> SkillCreateChoices:
    """Run the skill-create wizard and return the user's choices."""
    from vessal.ark.shell.tui.inline_prompt import ask_text, ask_yes_no

    print("Vessal skill scaffold wizard (press Enter to accept defaults, Ctrl-C to cancel)")
    print()

    name = ask_text(
        "Skill name (Python identifier)",
        default="my_skill",
        validator=validate_skill_name,
    )
    with_tutorial = ask_yes_no("Generate TUTORIAL.md?", default=True)
    with_ui = ask_yes_no("Generate ui/index.html (with example)?", default=True)
    with_server = ask_yes_no("Generate server.py (with example route)?", default=True)

    return SkillCreateChoices(
        name=name.strip(),
        with_tutorial=with_tutorial,
        with_ui=with_ui,
        with_server=with_server,
    )
