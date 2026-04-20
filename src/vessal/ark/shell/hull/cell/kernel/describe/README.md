# describe

Sub-package for rendering Python objects to text. This is an internal implementation detail of Kernel and should not be directly imported from outside Kernel.

Responsible for:
- render_value(obj, detail_level) -> str: renders any Python object at the specified detail level
- Three detail levels: directory (summary line), diff (truncated display), pin (detailed observation)
- Type dispatch: primitives / collections / callables / instances / binary

Not responsible for:
- Namespace rendering (handled by the render/ sub-package)
- Code execution (handled by executor.py)

## Design

describe exists to separate the concern of "how objects are converted to text" from executor (diff computation) and renderer (namespace display). Both need to convert Python objects to readable text; if each implemented this independently it would cause duplication and inconsistency.

The three detail levels come from different consumer scenarios: directory is for namespace directory display (one-line summary), diff is for change records (truncated but recognizable), pin is for pin observation (complete information).

Type dispatch is implemented via an explicit isinstance chain rather than a registry, because the number of Python built-in types is fixed; an explicit chain is clearer and faster. The __vessal_repr__ protocol allows third-party objects to customize rendering, with higher priority than built-in dispatch.

## Public Interface

### render_value(obj: object, detail_level: str) -> str

Renders a Python object to text at the specified detail level.


## File Structure

```
__init__.py          describe — namespace variable value rendering system.
binary.py            binary.py — bytes and module type rendering.
callables.py         callables.py — function and class rendering.
collections.py       collections.py — collection type rendering (list, dict, set, tuple).
instances.py         instances.py — instance, IO object, and connection-like object rendering.
primitives.py        primitives.py — primitive type rendering (int, float, bool, None, str).
```

## Dependencies

- `vessal.ark.shell.hull.cell.kernel.describe.binary`
- `vessal.ark.shell.hull.cell.kernel.describe.callables`
- `vessal.ark.shell.hull.cell.kernel.describe.collections`
- `vessal.ark.shell.hull.cell.kernel.describe.instances`
- `vessal.ark.shell.hull.cell.kernel.describe.primitives`


## Tests

_No test directory._


## Status

### TODO
None.

### Known Issues
None.

### Active
None.
