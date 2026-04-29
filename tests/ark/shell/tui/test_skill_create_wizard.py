"""test_skill_create_wizard — wizard collects 4 fields and validates name."""
from __future__ import annotations

from unittest.mock import patch

from vessal.ark.shell.tui.skill_create_wizard import (
    SkillCreateChoices,
    run_skill_create_wizard,
    validate_skill_name,
)


def test_validate_skill_name_rejects_non_identifier():
    assert validate_skill_name("") is not None
    assert validate_skill_name("2bad") is not None
    assert validate_skill_name("has-dash") is not None
    assert validate_skill_name("ok_name") is None


def test_wizard_returns_dataclass_with_all_fields():
    # Patch inline_prompt._prompt (used by ask_text and ask_yes_no) with sequential answers.
    # Answers: name="my_skill", tutorial=y, ui=n, server=y
    with patch(
        "vessal.ark.shell.tui.inline_prompt._prompt",
        side_effect=["my_skill", "y", "n", "y"],
    ):
        choices = run_skill_create_wizard()

    assert isinstance(choices, SkillCreateChoices)
    assert choices.name == "my_skill"
    assert choices.with_tutorial is True
    assert choices.with_ui is False
    assert choices.with_server is True
