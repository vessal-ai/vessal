"""skill.py — SystemSkill: built-in Kernel system-signal carrier."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from vessal.ark.shell.hull.cell.kernel import render_value
from vessal.ark.util.token_util import estimate_tokens
from vessal.skills._base import BaseSkill

if TYPE_CHECKING:
    from vessal.ark.shell.hull.cell.kernel.kernel import Kernel

logger = logging.getLogger(__name__)

_NAMESPACE_BUDGET = 4000  # tokens; same default as legacy namespace_dir signal


class SystemSkill(BaseSkill):
    """Built-in Skill that surfaces Kernel-owned signals to the Agent.

    Per spec §6.2, lives at `G["_system"]`. Hull writes wake reasons via
    set_wake(). signal_update() reads kernel.L on each call and assembles
    self.signal as a flat dict consumed by render._signal_render.
    """

    name = "_system"
    description = "kernel signals"

    def __init__(self) -> None:
        super().__init__()
        self._kernel: "Kernel | None" = None
        self._wake: str = ""
        print("_system: SystemSkill — kernel signals (frame, context, wake, errors)")

    def _bind_kernel(self, kernel: "Kernel") -> None:
        """Kernel calls this once after exec(boot_script) returns. Spec §7.4 / D6."""
        self._kernel = kernel

    # ---- Public API used by Hull ---------------------------------------
    def set_wake(self, reason: str) -> None:
        """Hull calls this to record why the current frame is being executed."""
        self._wake = str(reason or "")

    # ---- Kernel-driven scan --------------------------------------------
    def signal_update(self) -> None:
        if self._kernel is None:
            return  # not yet bound; signal stays {}
        L = self._kernel.L
        sig: dict[str, Any] = {}

        sig["frame"] = L.get("_frame", 0)

        ctx_pct = L.get("_context_pct", 0)
        budget_total = L.get("_budget_total", 0) or (
            L.get("_context_budget", 128000) - L.get("_token_budget", 4096)
        )
        used = round(budget_total * ctx_pct / 100) if ctx_pct else 0
        sig["context"] = f"{ctx_pct}% ({used}/{budget_total} tokens)"

        frame_type = L.get("_frame_type", "")
        if frame_type:
            sig["frame_type"] = frame_type

        if self._wake:
            sig["wake"] = self._wake

        verdict = L.get("verdict")
        if verdict is not None:
            verdict_text = f"{verdict.passed}/{verdict.total} assertions passed"
            if verdict.failures:
                verdict_text += "\n" + "\n".join(
                    f"  [{f.kind}] {f.assertion} — {f.message}"
                    for f in verdict.failures
                )
            sig["verdict"] = verdict_text

        errors = L.get("_errors", [])
        if errors:
            recent = errors[-3:]
            lines = [getattr(e, "summary", lambda: repr(e))() for e in recent]
            if len(errors) > 3:
                lines.insert(0, f"({len(errors)} errors, showing most recent 3)")
            sig["errors"] = "\n".join(lines)

        ns_text = self._render_namespace(L)
        if ns_text:
            sig["namespace"] = ns_text

        self.signal = sig

    # ---- Helpers --------------------------------------------------------
    def _render_namespace(self, L: dict, budget: int = _NAMESPACE_BUDGET) -> str:
        builtin_names = set(L.get("_builtin_names", []))
        ns_meta = L.get("_ns_meta", {})
        user_vars = [k for k in L if not k.startswith("_") and k not in builtin_names]
        if not user_vars:
            return "(empty)"

        def _key(name: str):
            meta = ns_meta.get(name)
            if meta:
                return (-meta.get("last_used", 0),)
            return (float("inf"),)

        user_vars.sort(key=_key)

        lines = [f"  {name}: {render_value(L[name], 'directory')}" for name in user_vars]
        result = "\n".join(lines)
        if estimate_tokens(result) <= budget:
            return result

        kept = []
        total = len(user_vars)
        for i, name in enumerate(user_vars):
            kept.append(f"  {name}: {render_value(L[name], 'directory')}")
            remaining = total - (i + 1)
            candidate = "\n".join(kept)
            if remaining > 0:
                candidate += f"\n  ...[{remaining} more variables]"
            if estimate_tokens(candidate) > budget:
                kept.pop()
                remaining = total - i
                suffix = f"\n  ...[{remaining} more variables]" if remaining > 0 else ""
                return "\n".join(kept) + suffix
        return "\n".join(kept)
