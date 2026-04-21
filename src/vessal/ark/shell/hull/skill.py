"""skill.py — Skill abstract base class: defines the interface contract that all Skills must implement."""
from __future__ import annotations

from abc import ABC


class SkillBase(ABC):
    """Skill abstract base class.

    Subclasses must define:
        name: str        — skill name
        description: str — one-line description (≤15 chars, function only, no method names)

    Optional overrides:
        guide: str      — methodology text (SKILL.md body, set by loader)
        _signal()       — called each frame, returns (title, body) or None
        _prompt()       — called each frame, returns (condition, methodology) cognitive protocol or None
        _bind_hull(hull)  — called once after the Skill lands in namespace, for Skills that need a Hull handle

    Creation rules:
        1. description ≤ 15 chars; describe function only, not method names.
        2. _signal() shows status info only; do not expose method signatures.
        3. SKILL.md guide is the only place containing method signatures; keep it concise.
        4. _prompt() contains behavioral rules only (when to use + methodology); no API reference.
        5. _prompt() changes must go through file (unload → edit file → reload); runtime modification not allowed.

    Modification policy:
        Agent may modify any Skill (including built-ins) via unload → edit file → load hot-reload.
        Built-in Skill modifications are overwritten on vessal package upgrade;
        persistent modifications should create a user Skill with the same name to override.

    Three information layers:
        _prompt()  → Persistent layer: behavioral rules injected into system prompt every frame, never lost.
        guide      → Manual layer: Agent prints on demand; re-print cost is 1 frame.
        _signal()  → Reminder layer: each frame reminds "print(name.guide) to view methods".

    Design rules:
        1. Protect internal state with _ prefix (_inbox, _cache, etc.) to prevent Agent from bypassing the API.
        2. All public methods callable by Agent must produce observable feedback (print output, return value,
           or namespace diff); otherwise Agent cannot tell if an operation succeeded and will fall into blind retries.
    """

    name: str
    description: str
    guide: str = ""

    def __init__(self):
        if type(self) is SkillBase:
            raise TypeError("SkillBase cannot be instantiated directly; subclass it and define name and description")

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Only validate non-abstract subclasses
        if not getattr(cls, "__abstractmethods__", set()):
            for attr in ("name", "description"):
                if not isinstance(getattr(cls, attr, None), str):
                    raise TypeError(
                        f"Skill class {cls.__name__!r} must define class attribute {attr!r}: str"
                    )

    def _signal(self) -> tuple[str, str] | None:
        """Called each frame. Returns (title, body) signal content, or None if there is nothing to show.

        Returns:
            (title, body) tuple or None. title is used to render a section heading; body is the signal content.
        """
        return None

    def _prompt(self) -> tuple[str, str] | None:
        """Called each frame. Returns (condition, methodology) cognitive protocol, or None if unused.

        condition: Activation condition — when to use this protocol.
        methodology: Methodology — what rules to follow.

        The renderer formats (condition, methodology) as:
            When {condition}:
            {methodology}

        Returns:
            (condition, methodology) tuple or None.
        """
        return None
