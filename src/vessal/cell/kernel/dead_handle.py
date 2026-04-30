"""DeadHandle — per-key snapshot fallback for unpicklable values (spec §5.5.2 档 1).

When Kernel.snapshot() finds a value that cloudpickle refuses, it replaces
the value with a DeadHandle. Snapshot completes successfully; restore brings
the DeadHandle back; any attribute access or call raises immediately so the
agent cannot silently treat a dead resource as live.
"""
from __future__ import annotations


class DeadHandle:
    __slots__ = ("kind", "origin", "reason")

    def __init__(self, kind: object, origin: object, reason: object) -> None:
        # Force everything through str() so __repr__ never accidentally invokes
        # another object's __repr__. Same defensive pattern as UnresolvedRef.
        object.__setattr__(self, "kind", str(kind))
        object.__setattr__(self, "origin", str(origin))
        object.__setattr__(self, "reason", str(reason))

    def __getstate__(self) -> dict:
        return {"kind": self.kind, "origin": self.origin, "reason": self.reason}

    def __setstate__(self, state: dict) -> None:
        for k, v in state.items():
            object.__setattr__(self, k, v)

    def __repr__(self) -> str:
        return f"<DeadHandle {self.kind} from {self.origin}: {self.reason}>"

    def __getattr__(self, name: str) -> "DeadHandle":
        kind = object.__getattribute__(self, "kind")
        reason = object.__getattribute__(self, "reason")
        raise RuntimeError(
            f"dead handle ({kind}) cannot be used: {reason}"
        )

    def __call__(self, *args: object, **kwargs: object) -> "DeadHandle":
        kind = object.__getattribute__(self, "kind")
        reason = object.__getattribute__(self, "reason")
        raise RuntimeError(
            f"dead handle ({kind}) cannot be used: {reason}"
        )
