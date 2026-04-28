"""_system Skill — surfaces Kernel-owned facts to the Agent via signal.

Lives at G['_system']. signal_update() reads authoritative sources only
(SQLite errors table, the kernel's own state, this Skill's own slots)
and never reads from L keys that the architecture has retired.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vessal.skills._base import BaseSkill

if TYPE_CHECKING:
    from vessal.ark.shell.hull.cell.kernel.kernel import Kernel

logger = logging.getLogger(__name__)


class SystemSkill(BaseSkill):
    """Built-in Skill carrying Kernel-side facts (frame number, sleep/wake,
    recent errors) into the per-frame signal stream."""

    name = "_system"
    description = "kernel signals (frame, sleep/wake, recent_errors)"

    def __init__(self) -> None:
        super().__init__()
        self._kernel: "Kernel | None" = None
        self._sleeping: bool = False
        self._wake_reason: str = ""
        print("_system: SystemSkill — frame / sleep / wake / recent_errors")

    def _bind_kernel(self, kernel: "Kernel") -> None:
        self._kernel = kernel

    # ---- Agent-facing + Hull-facing methods ------------------------------

    def sleep(self) -> None:
        """Agent calls this to mark itself sleeping."""
        self._sleeping = True

    def wake(self, reason: str = "") -> None:
        """Hull calls this when an external event wants to resume the agent."""
        self._sleeping = False
        self._wake_reason = str(reason or "")

    # ---- Kernel-driven scan ----------------------------------------------

    def signal_update(self) -> None:
        if self._kernel is None:
            return
        sig: dict = {"frame": self._kernel.L.get("_frame", 0)}

        if self._sleeping:
            sig["sleeping"] = True
        if self._wake_reason:
            sig["wake_reason"] = self._wake_reason

        if self._kernel.frame_log is not None:
            # avoid circular import at module load time
            from vessal.ark.shell.hull.cell.kernel.frame_log.reader import recent_errors
            entries = recent_errors(self._kernel.frame_log.conn, limit=3)
            if entries:
                sig["recent_errors"] = [
                    f"frame {e['n_start']} {e['source']}: "
                    + e["format_text"].strip().splitlines()[-1]
                    for e in entries
                ]

        self.signal = sig
