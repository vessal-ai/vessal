"""test_source_cache.py — Unit tests for source_cache.register() and reload_from_db()."""
from __future__ import annotations

import linecache
import sqlite3
import sys

import pytest

from vessal.ark.shell.hull.cell.kernel import source_cache
from vessal.ark.shell.hull.cell.kernel.frame_log.schema import DDL


@pytest.fixture
def clean_cache():
    """Remove any frame-* entries before and after each test."""
    yield
    for key in [k for k in list(linecache.cache.keys()) if k.startswith("<frame-")]:
        linecache.cache.pop(key, None)
    for key in [k for k in list(sys.modules.keys()) if k.startswith("<frame-")]:
        sys.modules.pop(key, None)


class TestRegister:
    def test_operation_inserted_under_frame_n(self, clean_cache):
        source_cache.register(7, "x = 1\n", None)
        assert "<frame-7>" in linecache.cache

    def test_operation_lines_preserve_newlines(self, clean_cache):
        source_cache.register(7, "x = 1\ny = 2\n", None)
        size, mtime, lines, fullname = linecache.cache["<frame-7>"]
        assert lines == ["x = 1\n", "y = 2\n"]
        assert fullname == "<frame-7>"

    def test_mtime_is_none(self, clean_cache):
        """mtime=None tells linecache 'never re-stat this entry'."""
        source_cache.register(7, "x = 1\n", None)
        _, mtime, _, _ = linecache.cache["<frame-7>"]
        assert mtime is None

    def test_size_matches_source_length(self, clean_cache):
        op = "x = 1\ny = 2\n"
        source_cache.register(7, op, None)
        size, _, _, _ = linecache.cache["<frame-7>"]
        assert size == len(op)

    def test_expect_inserted_under_frame_n_expect(self, clean_cache):
        source_cache.register(7, None, "assert x == 1\n")
        assert "<frame-7-expect>" in linecache.cache
        assert "<frame-7>" not in linecache.cache

    def test_both_inserted_when_both_present(self, clean_cache):
        source_cache.register(7, "x = 1\n", "assert x == 1\n")
        assert "<frame-7>" in linecache.cache
        assert "<frame-7-expect>" in linecache.cache

    def test_none_operation_skipped(self, clean_cache):
        source_cache.register(7, None, None)
        assert "<frame-7>" not in linecache.cache
        assert "<frame-7-expect>" not in linecache.cache

    def test_empty_string_skipped(self, clean_cache):
        """Empty operation is treated as 'no source' — no linecache entry."""
        source_cache.register(7, "", "")
        assert "<frame-7>" not in linecache.cache
        assert "<frame-7-expect>" not in linecache.cache

    def test_register_idempotent_overwrite(self, clean_cache):
        """Re-registering the same n with new text overwrites cleanly."""
        source_cache.register(7, "x = 1\n", None)
        source_cache.register(7, "x = 999\n", None)
        _, _, lines, _ = linecache.cache["<frame-7>"]
        assert lines == ["x = 999\n"]


class TestReloadFromDb:
    def _make_db(self, rows: list[tuple[int, str | None, str | None]]) -> sqlite3.Connection:
        """Build an in-memory SQLite with frame_log schema + the given rows."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(DDL)
        for n, op, exp in rows:
            conn.execute(
                "INSERT INTO frame_content(n, pong_operation, pong_expect) "
                "VALUES (?, ?, ?)",
                (n, op, exp),
            )
        conn.commit()
        return conn

    def test_returns_row_count(self, clean_cache):
        conn = self._make_db([(1, "a = 1\n", None), (2, "b = 2\n", "assert b == 2\n")])
        n = source_cache.reload_from_db(conn)
        assert n == 2

    def test_populates_operation_filenames(self, clean_cache):
        conn = self._make_db([(1, "a = 1\n", None), (2, "b = 2\n", None)])
        source_cache.reload_from_db(conn)
        assert "<frame-1>" in linecache.cache
        assert "<frame-2>" in linecache.cache

    def test_populates_expect_filenames(self, clean_cache):
        conn = self._make_db([(7, None, "assert x == 1\n")])
        source_cache.reload_from_db(conn)
        assert "<frame-7-expect>" in linecache.cache

    def test_skips_null_operation(self, clean_cache):
        conn = self._make_db([(7, None, None)])
        source_cache.reload_from_db(conn)
        assert "<frame-7>" not in linecache.cache
        assert "<frame-7-expect>" not in linecache.cache

    def test_empty_db_returns_zero(self, clean_cache):
        conn = self._make_db([])
        assert source_cache.reload_from_db(conn) == 0

    def test_reload_overwrites_stale_entries(self, clean_cache):
        """If linecache already has a stale '<frame-1>' entry, reload replaces it."""
        linecache.cache["<frame-1>"] = (5, None, ["stale\n"], "<frame-1>")
        conn = self._make_db([(1, "fresh = 1\n", None)])
        source_cache.reload_from_db(conn)
        _, _, lines, _ = linecache.cache["<frame-1>"]
        assert lines == ["fresh = 1\n"]
