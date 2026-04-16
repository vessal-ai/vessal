"""body.py — Agent avatar control.

Body manages the avatar's position, emotion, speech, and interaction options.
Methods called within a frame accumulate in an action queue; _drain() exports and clears the queue.
"""
from __future__ import annotations

import copy


class Body:
    """The Agent's body — hermit crab avatar."""

    def __init__(self):
        self.position: tuple[int, int] | str = (0, 0)
        self.emotion: str = "idle"
        self.speech: str = ""
        self._actions: list[dict] = []
        self._interactions: list[dict] = []

    # ── Agent interface ──

    def move_to(self, target: str | tuple[int, int]) -> None:
        """Move to a specified position or beside a UI element."""
        self.position = target
        self._actions.append({"type": "move", "target": target})

    def speak(self, text: str, duration: int = 3) -> None:
        """Show a speech bubble."""
        self.speech = text
        self._actions.append({"type": "speak", "text": text, "duration": duration})

    def emote(self, emotion: str) -> None:
        """Switch expression. Options: thinking, happy, working, idle, confused, sleeping"""
        self.emotion = emotion
        self._actions.append({"type": "emote", "emotion": emotion})

    def point_at(self, element_id: str) -> None:
        """Point at a UI element."""
        self._actions.append({"type": "point", "target": element_id})

    def offer_choices(self, options: list[str]) -> None:
        """Show choice bubbles and let the user pick one."""
        action = {"type": "offer_choices", "options": options}
        self._actions.append(action)
        self._interactions.append({"type": "choices", "options": options})

    def ask(self, prompt: str) -> None:
        """Pop up an input field for user text input."""
        action = {"type": "ask", "prompt": prompt}
        self._actions.append(action)
        self._interactions.append({"type": "ask", "prompt": prompt})

    # ── Internal ──

    def _serialize(self) -> dict:
        """Serialize to the body section of a render spec (read-only; does not clear)."""
        return {
            "state": {
                "position": self.position,
                "emotion": self.emotion,
                "speech": self.speech,
            },
            "actions": copy.deepcopy(self._actions),
            "interactions": copy.deepcopy(self._interactions),
        }

    def _drain(self) -> dict:
        """Export and clear the action queue and interactions; state is preserved."""
        spec = self._serialize()
        self._actions.clear()
        self._interactions.clear()
        return spec
