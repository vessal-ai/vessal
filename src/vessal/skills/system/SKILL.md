# _system — built-in Kernel signals

`_system` is a Vessal-internal Skill that surfaces Kernel-owned state to the Agent
on every frame. Lives at `G["_system"]`; never instantiate it manually.

## Signal payload keys

- `frame` (int) — current frame number
- `sleeping` (bool, optional) — present and True when the agent is sleeping
- `wake_reason` (str, optional) — reason the agent was woken (set by Hull via `wake()`)
- `recent_errors` (list[str], optional) — last N error summaries from the SQLite errors table

## Public API

### Agent-facing

- `sleep() -> None` — mark agent as sleeping; Hull's event loop pauses iteration

### Hull-facing

- `wake(reason: str = "") -> None` — resume the agent; `reason` flows into `signal["wake_reason"]`
