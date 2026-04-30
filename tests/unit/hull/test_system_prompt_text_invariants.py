"""Pin bare-name skill call bugs and frame field doc bugs in system.md.

Each assertion in this file corresponds to a specific bug class observed in
the wild (Agent trying sleep() then _system.sleep() over 2-3 frames, etc.).
A failure means a regression has reintroduced one of those bugs — fix the
prompt, do not relax the assertion."""

import re
from pathlib import Path

import pytest


PROMPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "src" / "vessal" / "hull" / "prompts" / "system.md"
)


@pytest.fixture(scope="module")
def prompt_text() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


# ---- Bare-name call bugs ----------------------------------------------------


def test_no_bare_sleep_call(prompt_text: str) -> None:
    """sleep() bare → not bound in namespace; must be _system.sleep()."""
    # Match `sleep(` only when NOT preceded by `.` (which would be a method call)
    # and not inside a comment/string discussing Python's time.sleep
    bare_calls = re.findall(r"(?<![.\w])sleep\(", prompt_text)
    assert len(bare_calls) == 0, (
        f"Found {len(bare_calls)} bare sleep() calls in system.md. "
        f"Must use _system.sleep() — sleep is not bound in the namespace."
    )


def test_system_sleep_taught(prompt_text: str) -> None:
    """The correct call form must be present in the prompt."""
    assert "_system.sleep()" in prompt_text, (
        "system.md must teach Agent to call _system.sleep() explicitly."
    )


def test_no_skills_dot_calls(prompt_text: str) -> None:
    """skills.list/load/unload → must be skill_manager.list/load/unload."""
    bad = re.findall(r"\bskills\.(list|load|unload)\(", prompt_text)
    assert len(bad) == 0, (
        f"Found references to skills.{set(bad)}() — Skill is bound as "
        f"skill_manager, not skills. Use skill_manager.list() etc."
    )


def test_skill_manager_taught(prompt_text: str) -> None:
    """The correct skill_manager API must be documented."""
    assert "skill_manager.list()" in prompt_text
    assert "skill_manager.load(" in prompt_text


# ---- Frame field documentation drift ----------------------------------------


def test_no_wake_or_task_frame_fields(prompt_text: str) -> None:
    """Composer does not render [wake] or [task] inside frames; doc must not claim it does."""
    # The doc shouldn't describe these as frame fields; they're auxiliary signals.
    # Match the bullet-list pattern from the Frame State Reading Guide block only.
    frame_doc_section = prompt_text.split("══════ Frame State Reading Guide ══════")[1]
    frame_doc_section = frame_doc_section.split("══════")[0]  # next block
    assert "`[wake]`" not in frame_doc_section, (
        "Frame State Reading Guide must not list [wake] as a frame field — "
        "Composer (composer.py:_compose_layer0) does not render it."
    )
    assert "`[task]`" not in frame_doc_section, (
        "Frame State Reading Guide must not list [task] as a frame field — "
        "Composer (composer.py:_compose_layer0) does not render it."
    )


def test_stderr_documented_as_frame_field(prompt_text: str) -> None:
    """Composer renders [stderr]; doc must list it."""
    frame_doc_section = prompt_text.split("══════ Frame State Reading Guide ══════")[1]
    frame_doc_section = frame_doc_section.split("══════")[0]
    assert "`[stderr]`" in frame_doc_section, (
        "Composer renders [stderr] in every frame with non-empty stderr; "
        "Frame State Reading Guide must document it."
    )


# ---- Signal section format drift --------------------------------------------


def test_signal_format_matches_composer(prompt_text: str) -> None:
    """Composer renders signals as `── Cls · var (scope) ──`, not `══════ Name ══════`.

    The documentation must teach the same format Agent will actually see, otherwise
    Agent's grep / regex over signals will silently miss matches.
    """
    # The new format example must be present somewhere in the file.
    assert re.search(r"── \w+ · \w+ \(\w+\) ──", prompt_text), (
        "system.md must include an example of the actual signal-section "
        "separator format used by Composer (── Cls · var (scope) ──)."
    )
