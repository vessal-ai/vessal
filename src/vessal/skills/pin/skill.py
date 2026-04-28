"""pin Skill — variable pinned-observation.

Pin subclasses BaseSkill and provides pin/unpin to surface variable values in every frame's signal.
Requires a ns reference to read arbitrary variable values.
"""
from __future__ import annotations

from vessal.ark.shell.hull import render_value
from vessal.skills._base import BaseSkill


class Pin(BaseSkill):
    """Variable pinned-observation Skill."""

    name = "pin"
    description = "watch pinned variables"

    def __init__(self, ns: dict | None = None):
        super().__init__()
        self._ns = ns
        self._pins: set[str] = set()

    def pin(self, name: str) -> None:
        """Add a variable to pinned observation."""
        self._pins.add(name)

    def unpin(self, name: str) -> None:
        """Remove a variable from pinned observation."""
        self._pins.discard(name)

    def signal_update(self) -> None:
        """Per-frame: render the current values of all pinned variables."""
        if not self._pins or self._ns is None:
            self.signal = {}
            return
        lines = []
        for name in sorted(self._pins):
            if name not in self._ns:
                lines.append(f"  [{name}: not found]")
            else:
                value_str = render_value(self._ns[name], "pin")
                lines.append(f"  {name} = {value_str}")
        text = "\n".join(lines)
        self.signal = {"pinned": text} if text else {}
