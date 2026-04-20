"""test_create_wizard_collision — R14 boot-surface regression.

Regression: ``vessal create`` must not emit a Python traceback when the chosen
project name collides with an existing directory.
Issue: console/1-active/20260420-cli-traceback-noise.md (D1 reproducer #1)
"""
from __future__ import annotations


def test_wizard_collision_never_prints_traceback(vessal_cli, tmp_path):
    (tmp_path / "agent_test").mkdir()
    # Scripted wizard answer order (validator loops the name step, so the
    # re-prompt happens BEFORE the LLM/dockerize questions):
    #   name                                 -> "agent_test"   (collides, re-prompt)
    #   name (re-prompt)                     -> "fresh_agent"  (accepted)
    #   api_key / base_url / model           -> blank (press enter x3)
    #   dockerize                            -> "n"
    stdin = "agent_test\nfresh_agent\n\n\n\nn\n"
    result = vessal_cli(["create"], stdin=stdin)

    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, f"Unexpected traceback:\n{combined}"
    # Validator error hint surfaced to the user
    assert "already exists" in combined
    # Wizard eventually succeeded after re-prompt
    assert (tmp_path / "fresh_agent").is_dir()
    assert result.returncode == 0
