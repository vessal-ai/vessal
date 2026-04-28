"""test_prompt_protocol.py — Unit tests for _prompt() cognitive protocol."""
import logging

from vessal.skills._base import BaseSkill


class ToolSkill(BaseSkill):
    """Pure tool Skill that does not override _prompt()."""
    name = "tool"
    description = "A tool skill"


class BehaviorSkill(BaseSkill):
    """Behavior Skill that overrides _prompt()."""
    name = "reviewer"
    description = "Code reviewer"

    def _prompt(self):
        return (
            "user submits code for you to review",
            "1. read the full diff first\n2. rank by correctness > security",
        )


def test_default_prompt_returns_none():
    """BaseSkill default _prompt() returns None."""
    skill = ToolSkill()
    assert skill._prompt() is None


def test_behavior_skill_returns_tuple():
    """Behavior Skill's _prompt() returns a (condition, methodology) 2-tuple."""
    skill = BehaviorSkill()
    result = skill._prompt()
    assert isinstance(result, tuple)
    assert len(result) == 2
    condition, methodology = result
    assert "review" in condition
    assert "correctness" in methodology


class FakePromptSource:
    """Non-BaseSkill subclass with a _prompt() method (duck-typing)."""
    name = "duck"

    def _prompt(self):
        return ("when X needs to be done", "follow method Y")


class ErrorPromptSource:
    """_prompt() raises an exception."""
    name = "broken"

    def _prompt(self):
        raise RuntimeError("boom")


def test_collect_skill_protocols_from_namespace():
    """Collect _prompt() return values from namespace."""
    from vessal.ark.shell.hull.cell.kernel.render._prompt_render import (
        collect_skill_protocols,
    )

    ns = {"reviewer": BehaviorSkill(), "tool": ToolSkill(), "x": 42}
    protocols = collect_skill_protocols(ns)
    assert len(protocols) == 1
    name, condition, methodology = protocols[0]
    assert name == "reviewer"
    assert "review" in condition


def test_collect_protocols_ducktype():
    """Non-BaseSkill objects with _prompt() are also collected."""
    from vessal.ark.shell.hull.cell.kernel.render._prompt_render import (
        collect_skill_protocols,
    )

    ns = {"duck": FakePromptSource()}
    protocols = collect_skill_protocols(ns)
    assert len(protocols) == 1
    assert protocols[0][0] == "duck"


def test_collect_protocols_error_does_not_crash():
    """An exception in _prompt() should not interrupt collection."""
    from vessal.ark.shell.hull.cell.kernel.render._prompt_render import (
        collect_skill_protocols,
    )

    ns = {"broken": ErrorPromptSource(), "good": FakePromptSource()}
    protocols = collect_skill_protocols(ns)
    assert len(protocols) == 1
    assert protocols[0][0] == "duck"


def test_render_skill_protocols_format():
    """Rendered format is ── name ──\\nWhen condition:\\nmethodology."""
    from vessal.ark.shell.hull.cell.kernel.render._prompt_render import (
        render_skill_protocols,
    )

    ns = {"reviewer": BehaviorSkill()}
    result = render_skill_protocols(ns)
    assert "── reviewer ──" in result
    assert "When " in result
    assert "correctness" in result


def test_render_skill_protocols_empty():
    """Returns empty string when there are no _prompt() sources."""
    from vessal.ark.shell.hull.cell.kernel.render._prompt_render import (
        render_skill_protocols,
    )

    ns = {"x": 42, "tool": ToolSkill()}
    result = render_skill_protocols(ns)
    assert result == ""


def test_collect_protocols_skips_empty_condition():
    """Protocol with empty condition string is skipped."""
    from vessal.ark.shell.hull.cell.kernel.render._prompt_render import collect_skill_protocols

    class EmptyConditionSkill:
        name = "empty_cond"

        def _prompt(self):
            return ("", "do something")

    ns = {"empty": EmptyConditionSkill()}
    protocols = collect_skill_protocols(ns)
    assert protocols == []
