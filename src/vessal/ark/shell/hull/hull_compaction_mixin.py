"""hull_compaction_mixin.py — Frame-stream compaction + snapshots for Hull.

Part of the Hull class via multiple-inheritance composition (see hull.py).
Methods here may assume the attributes set by Hull.__init__ are available via self.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import queue
    from concurrent.futures import ThreadPoolExecutor

    from vessal.ark.shell.hull.cell import Cell
    from vessal.ark.shell.hull.cell.core import Core
    from vessal.ark.shell.hull.cell.kernel import RenderConfig
    from vessal.ark.shell.hull.cell.protocol import Ping
    from vessal.ark.shell.hull.cell.kernel.render.prompt import SystemPromptBuilder
    from vessal.ark.shell.hull.event_loop import EventLoop
    from vessal.ark.shell.hull.hull_api import HullApi
    from vessal.ark.shell.hull.skill_loader import SkillLoader
    from vessal.ark.util.logging import Tracer

logger = logging.getLogger(__name__)


class HullCompactionMixin:
    """Frame-stream compaction and snapshot management for Hull."""

    def snapshot(self, path: str | None = None) -> str:
        """Save a snapshot to disk.

        Args:
            path: Snapshot file path. If None, auto-generates a timestamped filename under snapshots/.

        Returns:
            The actual file path written as a string.
        """
        from vessal.ark.shell.hull.skills_manifest import write_manifest
        if path is None:
            self._snapshots_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = str(self._snapshots_dir / f"{timestamp}.pkl")
        manifest_path = Path(path).with_suffix(".skills.json")
        write_manifest(manifest_path, self._skill_manager._loaded)
        self._cell.snapshot(path)
        return path

    def _restore_latest_snapshot(self) -> None:
        """Detect and restore the latest .pkl file under snapshots/. Silently skips if none exist."""
        from vessal.ark.shell.hull.skills_manifest import read_manifest
        if not self._snapshots_dir.exists():
            return
        snapshots = sorted(self._snapshots_dir.glob("*.pkl"))
        if not snapshots:
            return
        snap_path = snapshots[-1]
        manifest_path = snap_path.with_suffix(".skills.json")
        for name, info in read_manifest(manifest_path).items():
            parent = info.get("parent_path")
            if parent and parent not in sys.path:
                sys.path.insert(0, parent)
            stale = [k for k in sys.modules if k == name or k.startswith(name + ".")]
            for k in stale:
                del sys.modules[k]
        self._cell.restore(str(snap_path))

    def _resume_pending_compaction(self) -> None:
        """Re-submit any in-flight compaction that survived in the snapshot after a crash-restart."""
        fs = self._cell.get("_frame_stream")
        if fs is None:
            return
        if fs.compression_zone is None:
            return
        frame_number = self._cell.get("_frame", 0)
        payload = list(fs.compression_zone)
        task = {"layer": 0, "payload": payload}
        self._thread_pool.submit(self._run_compaction_task, task, frame_number)
        self._tracer.log(frame_number, "compaction.resumed", "event", 0, f"payload_n={len(payload)}")

    def _run_compaction_task(self, task: dict, frame_number: int) -> None:
        """Compaction worker body. Runs on the compaction thread. Must not touch ns."""
        import time
        from vessal.ark.shell.hull.cell.kernel.compression_parser import CompactionParseError, parse_compaction_json

        layer = task["layer"]
        payload = task["payload"]
        if not payload:
            self._result_queue.put(("skip", layer))
            return
        ping = self._build_compression_ping(payload, layer)
        t0 = time.monotonic()
        try:
            pong, _p, _c = self._compression_core.step(ping, tracer=self._tracer, frame=frame_number)
            raw_json = pong.action.operation
            record = parse_compaction_json(raw_json, layer=layer, compacted_at=frame_number)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            self._tracer.log(frame_number, "compaction.latency_ms", "span", elapsed_ms,
                             f"layer={layer}")
            self._result_queue.put((record.to_dict(), layer))
        except (CompactionParseError, Exception) as e:
            self._tracer.log(frame_number, "compaction.error", "worker", -1, f"layer={layer} err={e!r}")
            self._result_queue.put(("error", layer))

    def _build_compression_ping(self, payload: list[dict], layer: int) -> "Ping":
        """Assemble a compression Ping from a stripped frame or cold record payload."""
        from vessal.ark.shell.hull.cell.protocol import Ping, State
        from vessal.ark.shell.hull.cell.kernel.render._frame_render import project_frame_dict
        from vessal.ark.shell.hull.cell.kernel.render._cold_render import project_compaction_record

        if layer == 0:
            body = "\n\n".join(project_frame_dict(f) for f in payload)
        else:
            body = "\n\n".join(project_compaction_record(r) for r in payload)
        return Ping(
            system_prompt=self._compression_prompt,
            state=State(
                frame_stream="══════ frame stream ══════\n" + body,
                signals="",
            ),
        )
