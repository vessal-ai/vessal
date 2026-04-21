"""gate_base.py — Shared rule-management base for ActionGate and StateGate."""

from __future__ import annotations

from collections.abc import Callable


class _GateBase:
    """Mixin that owns rule storage and the three rule-management methods.

    Subclasses must not re-declare _rules, add_rule, remove_rule, or replace_rules.
    Each subclass keeps its own __init__ (for mode + builtin loading) and check().
    """

    _rules: list[tuple[str, Callable[[str], str | None]]]

    def add_rule(self, name: str, check_fn: Callable[[str], str | None]) -> None:
        """Register a custom rule.

        check_fn(content: str) -> str | None
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

    def replace_rules(self, rules: list[tuple[str, Callable[[str], str | None]]]) -> None:
        """Replace all rules atomically.

        Args:
            rules: New rule list. Each entry is a (name, check_fn) tuple.
        """
        self._rules = list(rules)
