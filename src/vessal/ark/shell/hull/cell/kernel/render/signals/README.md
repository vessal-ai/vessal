# signals

Kernel base signal module. Provides BASE_SIGNALS — the signal function list that always exists and does not depend on any Skill.

Responsible for:
- BASE_SIGNALS: five built-in signals (verdict, namespace directory, system, reconstruction hint, errors)
- Signal function protocol definition: fn(ns: dict) -> str, non-empty return indicates content

Not responsible for:
- Skill signal collection (handled by Kernel.update_signals())
- Signal concatenation rendering (handled by _signal_render.py)

## Design

BASE_SIGNALS exists to provide system-level state observation independent of Skills. Regardless of what Skills are loaded, these five signals always run: verdict (previous frame assertion results), namespace directory (user variable directory), system (key system variable status), reconstruction hint (cues when snapshot restore dropped non-serializable keys), errors (accumulated runtime and protocol errors).

The signal function protocol is minimal: fn(ns) -> str, returning empty string indicates no content. This protocol runs in parallel with the Skill's _signal() / _signal_output protocol; both are collected by Kernel.update_signals(), but BASE_SIGNALS does not require object instances.

## Public Interface

### BASE_SIGNALS

List of `(name, fn)` tuples — always-present signal functions that do not depend on any Skill. Each `fn(ns: dict) -> str` returns a non-empty string to emit content for the frame, or the empty string to skip.


## Tests

_No test directory._


## Status

### TODO
None.

### Known Issues
None.

### Active
None.
