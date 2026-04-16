"""ui Skill — cyber-embodied Agent.

Agent interface: body controls the avatar; component methods build the environment; render() updates the page; read() retrieves user events.
Shell interface: receive_event() delivers user actions; drain_outbox() retrieves render specs.
"""
from __future__ import annotations

from vessal.ark.shell.hull.skill import SkillBase
from vessal.skills.ui.body import Body
from vessal.skills.ui import components as _c


class UI(SkillBase):
    """Cyber-embodied Skill — the Agent's body and environment."""

    name = "ui"
    description = "control body and page"

    def __init__(self, ns=None):
        super().__init__()
        self.body = Body()
        self._components: list[dict] = []
        self._inbox: list[dict] = []
        self._outbox: list[dict] = []
        self._spec_version: int = 0

    # ── Agent interface ──

    def render(self, components: list) -> None:
        """Update page components and push a render spec."""
        self._components = list(components)
        body_spec = self.body._drain()
        # interactions hoisted to top level (frontend reads only top level); removed from body_spec to avoid duplication
        interactions = body_spec.pop("interactions", [])
        spec = {
            "body": body_spec,
            "components": self._components,
            "interactions": interactions,
            "version": self._spec_version,
        }
        self._outbox.append(spec)
        self._spec_version += 1

    def read(self) -> list[dict]:
        """Retrieve all pending user events and clear the inbox."""
        events = list(self._inbox)
        self._inbox.clear()
        return events

    def current_layout(self) -> dict:
        """Return the current page state (body + component tree)."""
        return {
            "body": self.body._serialize(),
            "components": list(self._components),
        }

    # ── Component factory methods ──

    def text(self, content: str, **props) -> dict:
        return _c.text(content, **props)

    def card(self, children: list, **props) -> dict:
        return _c.card(children, **props)

    def button(self, label: str, id: str, **props) -> dict:
        return _c.button(label, id=id, **props)

    def input(self, placeholder: str, id: str, **props) -> dict:
        return _c.input_field(placeholder, id=id, **props)

    def panel(self, title: str, children: list, **props) -> dict:
        return _c.panel(title, children, **props)

    def chart(self, data: list, kind: str = "bar", **props) -> dict:
        return _c.chart(data, kind=kind, **props)

    # ── Shell interface ──

    def receive_event(self, event: dict) -> None:
        """Deliver a user event to the inbox."""
        self._inbox.append(event)

    def drain_outbox(self) -> list[dict]:
        """Retrieve all pending render specs and clear the outbox."""
        specs = list(self._outbox)
        self._outbox.clear()
        return specs

    # ── Signal ──

    def _signal(self) -> tuple[str, str] | None:
        """Per-frame signal: body state + page layout summary + pending events."""
        lines = []

        # Body state
        pos = self.body.position
        pos_str = f"{pos[0]},{pos[1]}" if isinstance(pos, tuple) else pos
        lines.append(
            f"state: {self.body.emotion} | position: {pos_str}"
        )

        # Speech
        if self.body.speech:
            lines.append(f'"{self.body.speech}"')

        # Component summary
        if self._components:
            lines.append("page layout:")
            for comp in self._components:
                ctype = comp.get("type", "?")
                cid = comp.get("props", {}).get("id", "")
                title = comp.get("props", {}).get("title", "")
                label = title or cid or ""
                children_types = [
                    c.get("type", "?") for c in comp.get("children", [])
                ]
                children_str = ", ".join(children_types) if children_types else ""
                desc = f"  {ctype}"
                if label:
                    desc += f' "{label}"'
                if children_str:
                    desc += f": [{children_str}]"
                lines.append(desc)

        # Pending events
        n = len(self._inbox)
        if n > 0:
            event_summaries = []
            for e in self._inbox[:3]:
                etype = e.get("event", "?")
                eid = e.get("id", "")
                if eid:
                    event_summaries.append(f"{etype}: {eid}")
                else:
                    event_summaries.append(etype)
            summary = ", ".join(event_summaries)
            if n > 3:
                summary += f" +{n - 3}"
            lines.append(f"pending: {n} event(s) ({summary})")

        return ("ui", "\n".join(lines))

    # ── Prompt ──

    def _prompt(self) -> tuple[str, str] | None:
        """Cognitive protocol: guide the Agent to control body and environment."""
        return (
            "signal shows pending UI events, or there is new information to show the user",
            "1. First check pending events in signal; events must be handled with priority\n"
            "2. After reading events, decide next action based on content\n"
            "3. Express intent with the body (move, speak) before updating page content\n"
            "4. After each page update, call render() — otherwise the frontend sees no change\n"
            "5. When user input is needed, provide an interaction point via the body (choice bubbles or input field)",
        )
