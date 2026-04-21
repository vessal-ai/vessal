"""Tests for replace_rules on ActionGate and StateGate."""
from vessal.ark.shell.hull.cell.gate.action_gate import ActionGate
from vessal.ark.shell.hull.cell.gate.state_gate import StateGate


def test_action_gate_replace_rules_clears_then_appends():
    g = ActionGate(mode="auto")
    g.add_rule("r1", lambda op: None)
    assert len(g._rules) == 1

    g.replace_rules([])
    assert len(g._rules) == 0

    g.replace_rules([("r2", lambda op: None), ("r3", lambda op: None)])
    assert len(g._rules) == 2


def test_state_gate_replace_rules_clears_then_appends():
    g = StateGate(mode="auto")
    g.add_rule("r1", lambda s: None)
    assert len(g._rules) == 1

    g.replace_rules([])
    assert len(g._rules) == 0

    g.replace_rules([("r2", lambda s: None), ("r3", lambda s: None)])
    assert len(g._rules) == 2


def test_action_gate_replace_rules_is_atomic():
    """replace_rules replaces all rules including builtins, not appends."""
    g = ActionGate(mode="safe")
    builtin_count = len(g._rules)
    assert builtin_count > 0

    g.replace_rules([("custom", lambda op: None)])
    assert len(g._rules) == 1
    assert g._rules[0][0] == "custom"
