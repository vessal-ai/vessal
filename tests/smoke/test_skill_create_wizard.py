"""test_skill_create_wizard — R14 smoke test for the skill-create first-run flow."""
from __future__ import annotations

import argparse
from unittest.mock import patch


def test_skill_create_wizard_produces_full_scaffold(tmp_path, monkeypatch):
    """Bare `vessal skill create` with all-yes answers emits every conditional file."""
    monkeypatch.chdir(tmp_path)

    # Patch the underlying prompt_toolkit prompt used by ask_text / ask_yes_no.
    # Answers in order: name, tutorial (y), ui (y), server (y).
    with patch(
        "vessal.ark.shell.tui.inline_prompt._prompt",
        side_effect=["demo_skill", "y", "y", "y"],
    ):
        from vessal.ark.shell.cli.skill_cmds import _cmd_skill_create
        _cmd_skill_create(argparse.Namespace())

    skill_dir = tmp_path / "demo_skill"
    assert (skill_dir / "__init__.py").exists()
    assert (skill_dir / "skill.py").exists()
    assert (skill_dir / "SKILL.md").exists()
    assert (skill_dir / "requirements.txt").exists()
    assert (skill_dir / "tests" / "test_demo_skill.py").exists()
    assert (skill_dir / "TUTORIAL.md").exists()
    assert (skill_dir / "ui" / "index.html").exists()
    assert (skill_dir / "server.py").exists()


def test_skill_create_wizard_respects_no_flags(tmp_path, monkeypatch):
    """Answering no to tutorial/ui/server must skip those files."""
    monkeypatch.chdir(tmp_path)

    # Answers: name, tutorial (n), ui (n), server (n).
    with patch(
        "vessal.ark.shell.tui.inline_prompt._prompt",
        side_effect=["lean_skill", "n", "n", "n"],
    ):
        from vessal.ark.shell.cli.skill_cmds import _cmd_skill_create
        _cmd_skill_create(argparse.Namespace())

    skill_dir = tmp_path / "lean_skill"
    assert (skill_dir / "SKILL.md").exists()
    assert not (skill_dir / "TUTORIAL.md").exists()
    assert not (skill_dir / "ui").exists()
    assert not (skill_dir / "server.py").exists()
