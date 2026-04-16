"""prompt.py — Modular system_prompt assembly.

The Section model divides system_prompt into independent segments, sorted by priority for rendering.
Hull uses the builder to assemble the kernel protocol (protocol + capabilities),
and the renderer handles three-segment concatenation (kernel protocol → SOUL → skill protocol).

Standard two segments (managed by builder):
  priority=0   protocol     — framework runtime protocol (system.md)
  priority=20  capabilities — loaded Skill name+description (auto-generated)

SOUL and skill protocol are read from ns variables and concatenated by renderer.render().
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Section:
    """An independent segment of system_prompt, participating in assembly by priority.

    Attributes:
        name:     Segment name, unique identifier
        priority: Rendering order; lower value renders first
        required: When True, cannot be trimmed (reserved; trimming not currently implemented)
        render:   Render function with signature (ns: dict) -> str
    """
    name: str
    priority: int
    required: bool
    render: Callable[[dict], str]


class SystemPromptBuilder:
    """system_prompt assembler.

    Registers multiple Sections, build(ns) sorts and renders them by priority,
    skips empty content, and joins with '\\n\\n'.

    Attributes:
        _sections: List of registered Sections
    """

    def __init__(self) -> None:
        self._sections: list[Section] = []

    def register(self, section: Section) -> None:
        """Register a Section into the assembler.

        Args:
            section: Section instance to register.
        """
        self._sections.append(section)

    def build(self, ns: dict) -> str:
        """Render all Sections sorted by priority and join as system_prompt.

        Args:
            ns: Kernel namespace dict, passed to each Section.render().

        Returns:
            String of all non-empty Section texts joined with '\\n\\n'.
        """
        sorted_sections = sorted(self._sections, key=lambda s: s.priority)
        parts: list[str] = []
        for section in sorted_sections:
            text = section.render(ns)
            if text.strip():
                parts.append(text)
        return "\n\n".join(parts)


def _is_skill(obj: object) -> bool:
    """Duck-type check: whether the object implements the Skill protocol (name + description string attributes)."""
    return isinstance(getattr(obj, "name", None), str) and isinstance(
        getattr(obj, "description", None), str
    )


def render_capabilities(ns: dict) -> str:
    """Generate the capabilities section from Skill instances in the namespace.

    Scans all objects in ns that satisfy the Skill protocol (name + description string attributes),
    extracts name and description, and generates a Markdown list.
    Returns empty string when there are no Skills.

    Args:
        ns: Kernel namespace dict.

    Returns:
        Markdown-formatted loaded tools list string; returns "" when there are no Skills.
    """
    lines: list[str] = []
    for key, obj in ns.items():
        if _is_skill(obj):
            name = getattr(obj, "name", key)
            description = getattr(obj, "description", "")
            if description:
                lines.append(f"- `{name}` — {description}")
    if not lines:
        return ""
    return "## Loaded Tools\n\n" + "\n".join(sorted(lines))
