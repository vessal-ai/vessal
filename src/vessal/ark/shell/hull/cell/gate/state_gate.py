"""state_gate.py — Gate for state before it is sent to the LLM.

StateGate checks the state string before it is sent to Core.run().
Goal: intercept abnormally large context to protect API budget.

Design principles:
- Secure by default: built-in rules check obviously abnormal states
- Open to modification: users can add_rule() / remove_rule() to customize
- Does not block development: auto mode passes everything through
"""

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class StateGateResult:
    """Gate check result.

    Attributes:
        allowed: True means the state is permitted to be sent to the LLM, False means blocked.
        state:   Original state string (may be modified by rules).
        reason:  Reason for blocking (empty string when allowed=True).
    """

    __slots__ = ("allowed", "state", "reason")

    def __init__(self, allowed: bool, state: str, reason: str = "") -> None:
        self.allowed = allowed
        self.state = state
        self.reason = reason


class StateGate:
    """Safety gate for the state string before it is sent to the LLM.

    Three modes:
    - "auto":  no checking, pass through directly (for development/debugging)
    - "safe":  run built-in + custom rules, block abnormal states
    - "human": reserved for future human confirmation (currently equivalent to safe)

    Usage:
        gate = StateGate(mode="safe")
        result = gate.check(state)
        if not result.allowed:
            ns["_error"] = f"State gate blocked: {result.reason}"
    """

    def __init__(self, mode: str = "auto") -> None:
        """Initialize StateGate.

        Args:
            mode: Gate mode. "auto" passes all through; "safe"/"human" runs rule checks.
        """
        self.mode = mode
        self._rules: list[tuple[str, Callable[[str], str | None]]] = []

    def check(self, state: str) -> StateGateResult:
        """Check whether a state is permitted to be sent to the LLM.

        auto mode returns allowed=True immediately.
        safe/human mode runs all rules; if any blocks, returns allowed=False.

        Args:
            state: State string to check (rendered prompt).

        Returns:
            StateGateResult instance.
        """
        if self.mode == "auto":
            return StateGateResult(allowed=True, state=state)

        for rule_name, check_fn in self._rules:
            try:
                result = check_fn(state)
                if result is not None:
                    logger.info("state blocked by rule %r: %s", rule_name, result)
                    return StateGateResult(
                        allowed=False,
                        state=state,
                        reason=f"[{rule_name}] {result}",
                    )
            except Exception as e:
                logger.warning("gate rule %r raised exception: %s", rule_name, e)

        return StateGateResult(allowed=True, state=state)

    def add_rule(self, name: str, check_fn: Callable[[str], str | None]) -> None:
        """Register a custom rule.

        check_fn(state: str) -> str | None
        Return None to pass through; return a string to indicate the block reason.

        Args:
            name:     Rule name, used in logs and remove_rule.
            check_fn: Rule function.
        """
        self._rules.append((name, check_fn))

    def remove_rule(self, name: str) -> None:
        """Remove a rule by name.

        Args:
            name: Name of the rule to remove. Silently does nothing if not found.
        """
        self._rules = [(n, fn) for n, fn in self._rules if n != name]
