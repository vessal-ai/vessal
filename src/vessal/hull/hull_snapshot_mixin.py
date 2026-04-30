"""hull_snapshot_mixin.py — Snapshot management for Hull.

Part of the Hull class via multiple-inheritance composition (see hull.py).
Methods here may assume the attributes set by Hull.__init__ are available via self.
"""
from __future__ import annotations

from datetime import datetime


class HullSnapshotMixin:
    """Snapshot management for Hull."""

    def snapshot(self, path: str | None = None) -> str:
        """Save a snapshot for every Cell to disk.

        Args:
            path: Snapshot file path for the main Cell. If None, auto-generates a
                  timestamped filename under each Cell's own snapshots/ directory.

        Returns:
            The actual file path written for the main Cell.
        """
        from pathlib import Path

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        main_path = path
        for cell in self.cells:
            cell_snapshots_dir = Path(cell._data_dir) / "snapshots"
            cell_snapshots_dir.mkdir(parents=True, exist_ok=True)
            if cell is self._main_cell and main_path is not None:
                cell_path = main_path
            else:
                cell_path = str(cell_snapshots_dir / f"{timestamp}.pkl")
            cell.snapshot(cell_path)
            if cell is self._main_cell:
                main_path = cell_path
        return main_path

    def _latest_snapshot_path(self) -> str | None:
        """Pick the newest .pkl in data/<cell>/snapshots/. None if empty.

        Spec §5.1: snapshot bytes live in data/<cell>/snapshots/<ts>.pkl,
        sibling of frame_log.sqlite under the per-Cell data tree.
        """
        if not self._snapshots_dir.exists():
            return None
        snapshots = sorted(self._snapshots_dir.glob("*.pkl"))
        return str(snapshots[-1]) if snapshots else None
