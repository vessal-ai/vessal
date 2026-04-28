"""_base.py — BaseSkill: spec §6.1 contract for all Vessal Skills."""
from __future__ import annotations

from abc import ABC


class BaseSkill(ABC):
    """All Skills inherit from this class.

    Spec §6.1 contract:
        signal: dict        — instance attribute initialized in __init__ to {}
        signal_update()     — no-arg, no-return; updates self.signal each frame

    Class attributes (UX contract, not enforced at instance level):
        name: str           — short identifier
        description: str    — one-line, ≤15 chars, function only
        guide: str          — long-form manual (loaded from SKILL.md by Hull)

    Optional protocol methods:
        _prompt()       — (condition, methodology) tuple injected into system prompt
        _bind_hull(h)   — called once after the Skill lands in the namespace

    Spec §6.1 strong constraints (enforcement deferred to PR 4 boot frame):
        1. signal MUST be an instance attribute (set in __init__), not class attribute.
        2. signal_update is no-arg, no-return; side effect only.
        3. __init__ SHOULD print self-introduction (collected into boot frame stdout).
    """

    name: str
    description: str
    guide: str = ""

    def __init__(self) -> None:
        if type(self) is BaseSkill:
            raise TypeError(
                "BaseSkill cannot be instantiated directly; subclass it and define name/description"
            )
        self.signal: dict = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "__abstractmethods__", set()):
            for attr in ("name", "description"):
                if not isinstance(getattr(cls, attr, None), str):
                    raise TypeError(
                        f"Skill class {cls.__name__!r} must define class attribute {attr!r}: str"
                    )

    def signal_update(self) -> None:
        """Called once per ping by Kernel before render. Override to mutate self.signal."""
        pass

    def _prompt(self) -> tuple[str, str] | None:
        """Optional cognitive-protocol hook. Return (condition, methodology) or None."""
        return None
