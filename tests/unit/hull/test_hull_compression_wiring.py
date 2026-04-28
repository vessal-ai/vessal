"""test_hull_compression_wiring — Verify Hull initializes compression resources."""
from __future__ import annotations

import queue as queue_mod
from concurrent.futures import ThreadPoolExecutor

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


def test_hull_initializes_compression_core(tmp_path):
    from vessal.ark.shell.hull.cell.core import Core
    hull = _make_hull(tmp_path)
    assert isinstance(hull._compression_core, Core)


def test_hull_initializes_result_queue(tmp_path):
    hull = _make_hull(tmp_path)
    assert isinstance(hull._result_queue, queue_mod.Queue)


def test_hull_initializes_single_worker_pool(tmp_path):
    hull = _make_hull(tmp_path)
    assert isinstance(hull._thread_pool, ThreadPoolExecutor)
    assert hull._thread_pool._max_workers == 1


def test_hull_compression_prompt_loaded(tmp_path):
    hull = _make_hull(tmp_path)
    assert isinstance(hull._compression_prompt, str)
    assert len(hull._compression_prompt) > 0


def test_compaction_worker_produces_record(monkeypatch, tmp_path):
    import json
    from unittest.mock import MagicMock

    from vessal.ark.shell.hull.cell.protocol import Action, Pong, FRAME_SCHEMA_VERSION

    hull = _make_hull(tmp_path)

    valid_json = json.dumps({
        "range": [0, 0],
        "intent": "set up auth",
        "operations": ["hash pw"],
        "outcomes": "token issued",
        "artifacts": ["auth.py"],
        "notable": "",
    })
    fake_pong = Pong(think="", action=Action(operation=valid_json, expect=""))
    monkeypatch.setattr(hull._compression_core, "step", lambda *a, **kw: (fake_pong, None, None))

    frame = {
        "schema_version": FRAME_SCHEMA_VERSION,
        "number": 0,
        "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
        "pong": {"think": "", "action": {"operation": "pass", "expect": ""}},
        "observation": {"stdout": "", "diff": "", "error": None, "verdict": None},
    }
    task = {"layer": 0, "payload": [frame]}
    hull._run_compaction_task(task, frame_number=1)

    result = hull._result_queue.get(timeout=1)
    record_dict, layer = result
    assert layer == 0
    assert record_dict["intent"] == "set up auth"


def test_compaction_worker_skip_on_empty_payload(tmp_path):
    hull = _make_hull(tmp_path)
    task = {"layer": 0, "payload": []}
    hull._run_compaction_task(task, frame_number=1)
    sentinel, layer = hull._result_queue.get(timeout=1)
    assert sentinel == "skip"
    assert layer == 0


def test_compaction_worker_error_sentinel_on_bad_json(monkeypatch, tmp_path):
    from unittest.mock import MagicMock
    from vessal.ark.shell.hull.cell.protocol import Action, Pong, FRAME_SCHEMA_VERSION

    hull = _make_hull(tmp_path)
    fake_pong = Pong(think="", action=Action(operation="not json at all", expect=""))
    monkeypatch.setattr(hull._compression_core, "step", lambda *a, **kw: (fake_pong, None, None))

    frame = {
        "schema_version": FRAME_SCHEMA_VERSION,
        "number": 0,
        "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
        "pong": {"think": "", "action": {"operation": "pass", "expect": ""}},
        "observation": {"stdout": "", "diff": "", "error": None, "verdict": None},
    }
    task = {"layer": 0, "payload": [frame]}
    hull._run_compaction_task(task, frame_number=1)

    sentinel, layer = hull._result_queue.get(timeout=1)
    assert sentinel == "error"
    assert layer == 0
