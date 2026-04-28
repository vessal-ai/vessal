"""heartbeat skill — periodic heartbeat wake-up."""
from __future__ import annotations

from vessal.skills._base import BaseSkill


class Heartbeat(BaseSkill):
    """Periodic heartbeat wake-up Skill. Works with server.py timer to prevent the Agent from sleeping indefinitely.

    Attributes:
        name: skill registration name
        description: one-line skill description
        guide: operation guide visible to the Agent
    """

    name = "heartbeat"
    description = "heartbeat keep-alive"
    guide = "Background heartbeat service; no manual action required."
