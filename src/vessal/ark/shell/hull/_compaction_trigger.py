"""Hull-side compaction trigger query (cell/06-compaction.md §6.5).

After every successful main_cell.step(), Hull runs should_compact against the
main Cell's frame_log SQLite. If any layer has >= k uncovered entries (no
upper-layer entry fully encloses them), Hull calls compaction_cell.step() once.
"""

from __future__ import annotations

import sqlite3

# 32 layers covers far beyond ten-million-frame range at k=4.
_MAX_LAYER = 32

_UNCOVERED_COUNT_SQL = """
SELECT COUNT(*) FROM entries e
WHERE e.layer = ?
  AND NOT EXISTS (
    SELECT 1 FROM entries u
    WHERE u.layer > e.layer
      AND u.n_start <= e.n_start
      AND u.n_end   >= e.n_end
  )
"""


def should_compact(main_db_path: str, k: int = 4) -> bool:
    """True iff at least one layer in the main db has >= k uncovered entries."""
    conn = sqlite3.connect(main_db_path)
    try:
        for layer in range(_MAX_LAYER):
            (count,) = conn.execute(_UNCOVERED_COUNT_SQL, (layer,)).fetchone()
            if count >= k:
                return True
        return False
    finally:
        conn.close()
