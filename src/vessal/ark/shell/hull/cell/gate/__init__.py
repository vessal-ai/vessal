"""gate — safety gating module for action / state before execution.

Provides two independent gates:
- ActionGate: checks action code before it is sent to Kernel.exec_operation()
- StateGate: checks the state string before it is sent to Core.run()

Both gates support three modes:
- "auto":  pass through directly (default for development/debugging)
- "safe":  run built-in + custom rules
- "human": reserved for future human confirmation (currently equivalent to safe)
"""

from vessal.ark.shell.hull.cell.gate.action_gate import ActionGate, ActionGateResult
from vessal.ark.shell.hull.cell.gate.state_gate import StateGate, StateGateResult

__all__ = ["ActionGate", "ActionGateResult", "StateGate", "StateGateResult"]
