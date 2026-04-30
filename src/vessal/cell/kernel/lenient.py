"""lenient.py — UnresolvedRef placeholder + LenientUnpickler.

Spec: docs/architecture/kernel/05-persistence.md §5.4.

LenientUnpickler subclasses pickle.Unpickler and overrides find_class so
that by-reference resolution failures (ModuleNotFoundError / AttributeError /
ImportError) return an UnresolvedRef placeholder instead of raising.

UnresolvedRef's __repr__ is the entire disclosure mechanism: when Kernel
writes the boot frame, it calls repr() on each restored value; UnresolvedRef
returns a human-readable failure message inline. No side channel needed.

Hard invariant: UnresolvedRef.__repr__ MUST NEVER RAISE (spec §5.4 "repr must never raise").
All __init__ args are forced through str() to neutralize adversarial inputs.
"""
from __future__ import annotations

import pickle


class UnresolvedRef:
    """Placeholder for a by-reference target that could not be resolved
    on lenient restore."""

    __slots__ = ("module", "qualname", "reason")

    def __init__(self, module, qualname, reason) -> None:
        self.module = str(module)
        self.qualname = str(qualname)
        self.reason = str(reason)

    def __repr__(self) -> str:
        return f"<UnresolvedRef {self.module}.{self.qualname}: {self.reason}>"

    def __setstate__(self, state):
        pass  # Discard BUILD state — module/qualname/reason are already set by find_class

    def __getattr__(self, name: str):
        raise AttributeError(
            f"{self.module}.{self.qualname} unavailable: {self.reason}"
        )

    def __call__(self, *args, **kwargs):
        raise RuntimeError(
            f"{self.module}.{self.qualname} unavailable: {self.reason}"
        )


class LenientUnpickler(pickle.Unpickler):
    """Unpickler that returns UnresolvedRef instead of raising on
    by-reference resolution failure."""

    def find_class(self, module: str, qualname: str):
        try:
            return super().find_class(module, qualname)
        except (ModuleNotFoundError, AttributeError, ImportError) as e:
            # ImportError covers the rare case where a module exists but raises during
            # import (e.g., circular dependency, broken __init__.py).
            _module, _qualname, _reason = module, qualname, f"{type(e).__name__}: {e}"
            # Return a real type so the C pickle NEWOBJ opcode's isinstance(cls, type)
            # check passes. __new__ returns an UnresolvedRef so the constructed
            # object is the placeholder, not an instance of this synthetic class.
            class _Placeholder:
                def __new__(cls, *args, **kwargs):
                    return UnresolvedRef(_module, _qualname, _reason)
            return _Placeholder
