"""test_hull_hook_integration — Verify before/after frame hooks drive compaction submission and drain."""
from __future__ import annotations

import queue as queue_mod
from unittest.mock import MagicMock, patch

import pytest


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
    return Hull(str(tmp_path))


def test_after_frame_submits_on_try_shift(tmp_path):
    """When try_shift returns a task, _thread_pool.submit is called once."""
    hull = _make_hull(tmp_path)
    fs = hull._cell.L.get("_frame_stream")
    fake_task = {"layer": 0, "payload": []}
    fs.try_shift = MagicMock(return_value=fake_task)

    submitted = []
    hull._thread_pool.submit = lambda fn, *a, **kw: submitted.append((fn, a))

    hull._after_frame()
    assert len(submitted) == 1
    assert submitted[0][0].__func__ is hull._run_compaction_task.__func__


def test_after_frame_no_submit_when_try_shift_none(tmp_path):
    """When try_shift returns None, submit is not called."""
    hull = _make_hull(tmp_path)
    fs = hull._cell.L.get("_frame_stream")
    fs.try_shift = MagicMock(return_value=None)

    submitted = []
    hull._thread_pool.submit = lambda fn, *a, **kw: submitted.append((fn, a))

    hull._after_frame()
    assert submitted == []


def test_before_frame_drains_result_queue_on_success(tmp_path):
    """Successful result in queue triggers apply_results on FrameStream."""
    hull = _make_hull(tmp_path)
    fs = hull._cell.L.get("_frame_stream")
    fs._in_flight = True

    applied = []
    fs.apply_results = MagicMock(side_effect=lambda r: applied.extend(r))

    record = {
        "schema_version": 7,
        "range": [0, 15],
        "intent": "test",
        "operations": [],
        "outcomes": "",
        "artifacts": [],
        "notable": "",
        "layer": 0,
        "compacted_at": 16,
    }
    hull._result_queue.put((record, 0))
    hull._rewrite_runtime_owned()

    assert len(applied) == 1
    assert applied[0] == (record, 0)


def test_before_frame_aborts_on_error_sentinel(tmp_path):
    """Error sentinel in queue calls abort_compaction."""
    hull = _make_hull(tmp_path)
    fs = hull._cell.L.get("_frame_stream")
    fs._in_flight = True

    aborted = []
    fs.abort_compaction = MagicMock(side_effect=lambda: aborted.append(True))
    fs.apply_results = MagicMock()

    hull._result_queue.put(("error", 0))
    hull._rewrite_runtime_owned()

    assert aborted == [True]
    fs.apply_results.assert_not_called()


def test_after_frame_hook_wired_in_event_loop(tmp_path):
    """Hull._event_loop._hooks.after_frame is hull._after_frame."""
    hull = _make_hull(tmp_path)
    hooks = hull._event_loop._hooks
    assert hooks.after_frame is not None


def test_periodic_snapshot_fires_every_n_frames(tmp_path, monkeypatch):
    """Snapshot fires when _compaction_frames_since_snapshot reaches N."""
    hull = _make_hull(tmp_path)
    hull._compaction_snapshot_every_n = 3

    snapshots = []
    monkeypatch.setattr(hull, "snapshot", lambda: snapshots.append(1))

    # try_shift always returns None (hot-only path, no compaction)
    fs = hull._cell.L.get("_frame_stream")
    fs.try_shift = MagicMock(return_value=None)

    for _ in range(7):
        hull._after_frame()

    # 7 frames with N=3: snapshot fires at frame 3 and 6 → 2 times
    assert len(snapshots) == 2
