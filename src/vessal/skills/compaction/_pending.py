"""PendingView / PendingGroup — the read-side data shape returned by
CompactionSkill.read_pending(). See docs/architecture/cell/06-compaction.md §6.3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PendingGroup:
    """One contiguous chunk of source-layer entries ready to be folded into a
    single layer-(L+1) summary.

    Attributes:
        layer:   source layer (0 = raw frames, 1 = L_1 summaries, ...).
        n_start: smallest n in the group.
        n_end:   largest n in the group.
        items:   per-entry payload — for layer=0 a dict of frame fields,
                 for layer>=1 the YAML body string.
    """
    layer: int
    n_start: int
    n_end: int
    items: list[Any]


@dataclass(frozen=True, slots=True)
class PendingView:
    """Snapshot of all pending groups across all layers, returned by read_pending."""
    groups: list[PendingGroup]
