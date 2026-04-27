"""test_prompt — SystemPromptBuilder unit tests."""
from vessal.ark.shell.hull.cell.kernel.render.prompt import Section, SystemPromptBuilder


def test_empty_builder_returns_empty():
    """Returns empty string when there are no Sections."""
    builder = SystemPromptBuilder()
    assert builder.build({}) == ""


def test_single_section():
    """Single Section renders correctly."""
    builder = SystemPromptBuilder()
    builder.register(Section("test", 0, True, lambda ns: "hello"))
    assert builder.build({}) == "hello"


def test_sections_ordered_by_priority():
    """Sections are sorted in ascending order by priority."""
    builder = SystemPromptBuilder()
    builder.register(Section("b", 10, True, lambda ns: "second"))
    builder.register(Section("a", 0, True, lambda ns: "first"))
    result = builder.build({})
    assert result == "first\n\nsecond"


def test_empty_render_skipped():
    """Sections whose render returns empty string are excluded from output."""
    builder = SystemPromptBuilder()
    builder.register(Section("filled", 0, True, lambda ns: "content"))
    builder.register(Section("empty", 10, True, lambda ns: ""))
    result = builder.build({})
    assert result == "content"


def test_render_receives_ns():
    """render function receives the namespace dict."""
    builder = SystemPromptBuilder()
    builder.register(Section("greet", 0, True, lambda ns: f"hello {ns.get('name', '')}"))
    result = builder.build({"name": "Alice"})
    assert result == "hello Alice"


def test_capabilities_section_from_skills():
    """capabilities Section generates a Skill list from SkillBase instances."""
    from vessal.ark.shell.hull.cell.kernel.render.prompt import render_capabilities
    from vessal.skills.chat.skill import Chat

    ns = {"chat": Chat(), "plain_var": 42}
    text = render_capabilities(ns)
    assert "chat" in text
    assert "42" not in text
