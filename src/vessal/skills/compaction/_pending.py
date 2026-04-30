"""PendingView / PendingGroup — the read-side data shape returned by
Compaction.read_pending(). See docs/architecture/cell/06-compaction.md §6.3."""

from __future__ import annotations

import sqlite3
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


K = 4
MAX_LAYER = 32

UNCOVERED_SQL = """
SELECT n_start, n_end
FROM entries e
WHERE e.layer = ?
  AND NOT EXISTS (
    SELECT 1 FROM entries u
    WHERE u.layer > e.layer
      AND u.n_start <= e.n_start
      AND u.n_end   >= e.n_end
  )
ORDER BY n_start ASC
"""


def fetch_uncovered_on_layer(conn: sqlite3.Connection, layer: int) -> list[tuple[int, int]]:
    return [tuple(row) for row in conn.execute(UNCOVERED_SQL, (layer,))]
