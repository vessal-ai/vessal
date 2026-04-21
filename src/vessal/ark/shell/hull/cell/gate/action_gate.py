"""action_gate.py — Safety gate for action before execution.

ActionGate checks action code before it is sent to Kernel.exec_operation().
Goal: intercept high-risk operations and protect the host environment.

Design principles:
- Secure by default: built-in rules intercept obviously dangerous operations
- Open to modification: users can add_rule() / remove_rule() to customize
- Does not block development: auto mode passes everything through
- Avoids over-detection: only intercepts operations that are almost certainly
  not legitimate Agent behavior
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from vessal.ark.shell.hull.cell.gate.gate_base import _GateBase

logger = logging.getLogger(__name__)


class ActionGateResult:
    """Gate check result.

    Attributes:
        allowed: True means execution is permitted, False means blocked.
        action:  Original action string.
        reason:  Reason for blocking (empty string when allowed=True).
    """

    __slots__ = ("allowed", "action", "reason")

    def __init__(self, allowed: bool, action: str, reason: str = "") -> None:
        self.allowed = allowed
        self.action = action
        self.reason = reason


class ActionGate(_GateBase):
    """Safety gate for action code before execution.

    Three modes:
    - "auto":  no checking, pass through directly (for development/debugging)
    - "safe":  run built-in + custom rules, block high-risk operations
    - "human": reserved for future human confirmation (currently equivalent to safe)

    Usage:
        gate = ActionGate(mode="safe")
        result = gate.check(action)
        if not result.allowed:
            ns["_error"] = f"Gate blocked: {result.reason}"
    """

    def __init__(self, mode: str = "auto") -> None:
        """Initialize ActionGate.

        Args:
            mode: Gate mode. "auto" passes all through; "safe"/"human" runs rule checks.
        """
        self.mode = mode
        self._rules: list[tuple[str, Callable[[str], str | None]]] = []
        if mode != "auto":
            self._load_builtin_rules()

    def check(self, action: str) -> ActionGateResult:
        """Check whether an action is permitted to execute.

        auto mode returns allowed=True immediately.
        safe/human mode runs all rules; if any blocks, returns allowed=False.

        Args:
            action: Python code string to check.

        Returns:
            ActionGateResult instance.
        """
        if self.mode == "auto":
            return ActionGateResult(allowed=True, action=action)

        for rule_name, check_fn in self._rules:
            try:
                result = check_fn(action)
                if result is not None:
                    logger.info("action blocked by rule %r: %s", rule_name, result)
                    return ActionGateResult(
                        allowed=False,
                        action=action,
                        reason=f"[{rule_name}] {result}",
                    )
            except Exception as e:
                logger.warning("gate rule %r raised exception: %s", rule_name, e)

        return ActionGateResult(allowed=True, action=action)

    def _load_builtin_rules(self) -> None:
        """Load the built-in safety rules."""
        from vessal.ark.shell.hull.cell.gate.rules import BUILTIN_RULES

        for rule_name, fn in BUILTIN_RULES:
            self._rules.append((rule_name, fn))  # type: ignore[arg-type]
