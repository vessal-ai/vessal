"""test_hull_compaction_metrics — Verify 6 Tracer metrics are emitted at correct sites."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


class MockTracer:
    def __init__(self):
        self.logs: list[dict] = []

    def log(self, frame: int, phase: str, event: str, duration_ms: int = -1, details: str = "") -> None:
        self.logs.append({"frame": frame, "phase": phase, "event": event,
                          "duration_ms": duration_ms, "details": details})

    def start(self, *a, **kw): ...
    def end(self, *a, **kw): ...
    def init(self, *a, **kw): ...

    def phases(self, name: str) -> list[dict]:
        return [r for r in self.logs if r["phase"] == name]


def _make_hull(tmp_path):
    (tmp_path / "hull.toml").write_text(
        '[agent]\nname = "test"\n[cell]\n[hull]\nskills = []\n',
        encoding="utf-8",
    )
    (tmp_path / "SOUL.md").write_text("# test", encoding="utf-8")
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=fake\nOPENAI_BASE_URL=http://fake\nOPENAI_MODEL=fake\n",
        encoding="utf-8",
    )
    from vessal.ark.shell.hull.hull import Hull
    hull = Hull(str(tmp_path))
    tracer = MockTracer()
    hull._tracer = tracer
    return hull, tracer


def test_metric_shift_blocked_emitted(tmp_path):
    """compaction.shift_blocked emitted when B_0 >= k and in_flight."""
    hull, tracer = _make_hull(tmp_path)
    fs = hull._cell.get("_frame_stream")
    fs._in_flight = True
    # Fill B_0 to exactly k frames
    dummy = {"schema_version": 7, "number": 0,
             "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
             "pong": {"think": "", "action": {"operation": "", "expect": ""}},
             "observation": {"stdout": "", "diff": "", "error": None, "verdict": None}}
    fs._hot[0] = [dummy] * fs.k
    fs.try_shift = MagicMock(return_value=None)

    hull._after_frame()
    blocked = tracer.phases("compaction.shift_blocked")
    assert len(blocked) == 1
    assert "value=1" in blocked[0]["details"]


def test_metric_in_flight_gauge_emitted(tmp_path):
    """compaction.in_flight emitted after try_shift succeeds."""
    hull, tracer = _make_hull(tmp_path)
    fs = hull._cell.get("_frame_stream")
    fake_task = {"layer": 0, "payload": []}
    fs.try_shift = MagicMock(return_value=fake_task)
    hull._thread_pool.submit = MagicMock()

    hull._after_frame()
    in_flight = tracer.phases("compaction.in_flight")
    assert len(in_flight) >= 1
    assert "value=1" in in_flight[0]["details"]


def test_metric_layer_stats_emitted_on_drain(tmp_path):
    """compaction.layer_stats emitted when result queue is drained successfully."""
    hull, tracer = _make_hull(tmp_path)
    fs = hull._cell.get("_frame_stream")
    fs._in_flight = True
    fs.apply_results = MagicMock()

    record = {
        "schema_version": 7, "range": [0, 15], "intent": "t",
        "operations": [], "outcomes": "", "artifacts": [], "notable": "",
        "layer": 0, "compacted_at": 16,
    }
    hull._result_queue.put((record, 0))
    hull._rewrite_runtime_owned()

    layer_stats = tracer.phases("compaction.layer_stats")
    assert len(layer_stats) >= 1


def test_metric_latency_ms_emitted_on_worker_completion(tmp_path):
    """compaction.latency_ms emitted with non-negative duration from _run_compaction_task."""
    from vessal.ark.shell.hull.cell.protocol import Action, Pong

    hull, tracer = _make_hull(tmp_path)
    valid_json = json.dumps({
        "range": [0, 0], "intent": "x", "operations": [],
        "outcomes": "", "artifacts": [], "notable": "",
    })
    fake_pong = Pong(think="", action=Action(operation=valid_json, expect=""))
    hull._compression_core.step = MagicMock(return_value=(fake_pong, None, None))

    from vessal.ark.shell.hull.cell.protocol import FRAME_SCHEMA_VERSION
    frame = {
        "schema_version": FRAME_SCHEMA_VERSION, "number": 0,
        "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
        "pong": {"think": "", "action": {"operation": "pass", "expect": ""}},
        "observation": {"stdout": "", "diff": "", "error": None, "verdict": None},
    }
    task = {"layer": 0, "payload": [frame], "raw_bytes": 100, "stripped_bytes": 80}
    hull._run_compaction_task(task, frame_number=1)

    latency = tracer.phases("compaction.latency_ms")
    assert len(latency) >= 1
    assert latency[0]["duration_ms"] >= 0


def test_metric_stripping_ratio_emitted_after_hot_shift(tmp_path):
    """compaction.stripping_ratio emitted when task has raw_bytes/stripped_bytes."""
    hull, tracer = _make_hull(tmp_path)
    fs = hull._cell.get("_frame_stream")
    task = {"layer": 0, "payload": [], "raw_bytes": 200, "stripped_bytes": 50}
    fs.try_shift = MagicMock(return_value=task)
    hull._thread_pool.submit = MagicMock()

    hull._after_frame()
    ratio_logs = tracer.phases("compaction.stripping_ratio")
    assert len(ratio_logs) >= 1
    assert "raw=200" in ratio_logs[0]["details"]
    assert "stripped=50" in ratio_logs[0]["details"]
