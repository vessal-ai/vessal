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
