# signals

Kernel base signal module. Provides BASE_SIGNALS — the signal function list that always exists and does not depend on any Skill.

Responsible for:
- BASE_SIGNALS: four built-in signals (verdict, namespace_dir, system_vars, compressed_history)
- Signal function protocol definition: fn(ns: dict) -> str, non-empty return indicates content

Not responsible for:
- Skill signal collection (handled by Kernel.update_signals())
- Signal concatenation rendering (handled by _signal_render.py)

## Design

BASE_SIGNALS exists to provide system-level state observation independent of Skills. Regardless of what Skills are loaded, these four signals always run: verdict (previous frame assertion results), namespace_dir (user variable directory), system_vars (key system variable status), compressed_history (summary of history outside the frame stream window).

The signal function protocol is minimal: fn(ns) -> str, returning empty string indicates no content. This protocol runs in parallel with the Skill's _signal() / _signal_output protocol; both are collected by Kernel.update_signals(), but BASE_SIGNALS does not require object instances.

## Public Interface

### BASE_SIGNALS

_Definition not found._


## File Structure

```
__init__.py          signals/__init__.py — Kernel base signal module.
compressed_history.py compressed_history.py — compressed history signal (built-in).
namespace_dir.py     namespace_dir.py — namespace directory view rendering (kernel/signals version).
system_vars.py       system_vars.py — system variable rendering (kernel/signals version).
verdict.py           verdict.py — validation result signal (kernel/signals version).
```

## Dependencies

- `vessal.ark.shell.hull.cell.kernel.describe`
- `vessal.ark.shell.hull.cell.kernel.render.signals`
- `vessal.ark.util.token_util`


## Tests

_No test directory._


## Status

### TODO
None.

### Known Issues
None.

### Active
None.
