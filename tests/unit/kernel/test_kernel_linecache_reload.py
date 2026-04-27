"""test_kernel_linecache_reload.py — Kernel reloads linecache from db on boot.

Scenario: A previous run wrote frames 1..3 to a SQLite frame_log. A new
process opens Kernel(db_path=…); the linecache must be repopulated with
those frames' operation and expect text so inspect.getsource() works on
any class restored from a cloudpickle snapshot whose co_filename points
back at one of those frames.
"""
from __future__ import annotations

import inspect
import linecache
import sqlite3
import sys
from pathlib import Path

import pytest

from vessal.ark.shell.hull.cell.kernel import Kernel
from vessal.ark.shell.hull.cell.kernel.frame_log.schema import DDL


@pytest.fixture
def clean_cache():
    yield
    for key in [k for k in list(linecache.cache.keys()) if k.startswith("<frame-")]:
        linecache.cache.pop(key, None)
    for key in [k for k in list(sys.modules.keys()) if k.startswith("<frame-")]:
        sys.modules.pop(key, None)


def _seed_db(path: Path, rows: list[tuple[int, str | None, str | None]]) -> None:
    """Initialize a frame_log database and insert frame_content rows."""
    conn = sqlite3.connect(str(path))
    conn.executescript(DDL)
    for n, op, exp in rows:
        conn.execute(
            "INSERT INTO frame_content(n, pong_operation, pong_expect) "
            "VALUES (?, ?, ?)",
            (n, op, exp),
        )
        conn.execute(
            "INSERT INTO entries(layer, n_start, n_end) VALUES (0, ?, ?)",
            (n, n),
        )
    conn.commit()
    conn.close()


class TestKernelLinecacheReload:
    def test_reload_populates_operation_filename(self, tmp_path, clean_cache):
        db = tmp_path / "frame_log.sqlite"
        _seed_db(db, [(1, "x = 1\n", None), (2, "y = 2\n", None)])

        Kernel(db_path=str(db))

        assert linecache.getlines("<frame-1>") == ["x = 1\n"]
        assert linecache.getlines("<frame-2>") == ["y = 2\n"]

    def test_reload_populates_expect_filename(self, tmp_path, clean_cache):
        db = tmp_path / "frame_log.sqlite"
        _seed_db(db, [(7, None, "assert x == 1\n")])

        Kernel(db_path=str(db))

        assert linecache.getlines("<frame-7-expect>") == ["assert x == 1\n"]

    def test_no_db_no_reload(self, clean_cache):
        """Constructing Kernel without db_path must not write linecache entries."""
        for k in [k for k in linecache.cache.keys() if k.startswith("<frame-")]:
            linecache.cache.pop(k)

        Kernel()  # no db_path

        added = [k for k in linecache.cache.keys() if k.startswith("<frame-")]
        assert added == []

    def test_inspect_getsource_works_after_reload(self, tmp_path, clean_cache):
        """End-to-end: a class whose co_filename points at <frame-42> can have
        its source retrieved by inspect.getsource after Kernel boots from db."""
        db = tmp_path / "frame_log.sqlite"
        op = "class Planner:\n    def plan(self):\n        return ['draft']\n"
        _seed_db(db, [(42, op, None)])

        Kernel(db_path=str(db))

        compiled = compile(op, "<frame-42>", "exec")
        ns: dict = {}
        ns["__name__"] = "<frame-42>"
        exec(compiled, ns)
        Planner = ns["Planner"]

        src = inspect.getsource(Planner)
        assert "class Planner" in src
        assert "return ['draft']" in src
