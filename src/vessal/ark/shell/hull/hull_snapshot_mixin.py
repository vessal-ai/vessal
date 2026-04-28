"""hull_snapshot_mixin.py — Snapshot management for Hull.

Part of the Hull class via multiple-inheritance composition (see hull.py).
Methods here may assume the attributes set by Hull.__init__ are available via self.
"""
from __future__ import annotations

from datetime import datetime


class HullSnapshotMixin:
    """Snapshot management for Hull."""

    def snapshot(self, path: str | None = None) -> str:
        """Save a snapshot to disk.

        Args:
            path: Snapshot file path. If None, auto-generates a timestamped filename under snapshots/.

        Returns:
            The actual file path written as a string.
        """
        if path is None:
            self._snapshots_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = str(self._snapshots_dir / f"{timestamp}.pkl")
        self._cell.snapshot(path)
        return path

    def _latest_snapshot_path(self) -> str | None:
        """Pick the newest .pkl in data/<cell>/snapshots/. None if empty.

        Spec §5.1: snapshot bytes live in data/<cell>/snapshots/<ts>.pkl,
        sibling of frame_log.sqlite under the per-Cell data tree.
        """
        if not self._snapshots_dir.exists():
            return None
        snapshots = sorted(self._snapshots_dir.glob("*.pkl"))
        return str(snapshots[-1]) if snapshots else None
