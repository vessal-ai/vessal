# _system — built-in Kernel signals

`_system` is a Vessal-internal Skill that surfaces Kernel-owned state to the Agent
on every frame. Lives at `G["_system"]`; never instantiate it manually.

## Signal payload keys

- `frame` (int) — current frame number
- `context` (str) — token utilization summary
- `frame_type` (str, optional) — frame kind tag
- `wake` (str, optional) — reason this frame was triggered (set by Hull)
- `verdict` (str, optional) — last expect-block result
- `errors` (str, optional) — recent ErrorRecord summary tail
- `namespace` (str) — directory view of user variables in L
- `dropped` (str, optional) — variables lost on last snapshot fallback

## Public API (Hull-only)

- `set_wake(reason: str) -> None` — record why the current frame is executing.
