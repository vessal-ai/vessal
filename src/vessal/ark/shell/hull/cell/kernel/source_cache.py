"""source_cache.py — linecache registration so inspect.getsource works on agent-defined classes.

Mechanism:
    linecache.cache is a stdlib dict mapping filename → (size, mtime, lines, fullname).
    inspect.getsource() and traceback both read from it. We register one entry per
    (frame, source-kind) using the filename the corresponding compile() call uses
    (`<frame-N>` for operation, `<frame-N-expect>` for expect). After register,
    inspect.getsource(SomeClass) where SomeClass.__code__.co_filename == '<frame-7>'
    transparently returns the operation text from frame 7.

    mtime is set to None so linecache never tries to stat() the non-existent file.

Public API:
    register(n, operation, expect) — write up to two cache entries for one frame
    reload_from_db(conn)            — replay register() for every row in frame_content
"""
from __future__ import annotations

import linecache
import sqlite3


def register(n: int, operation: str | None, expect: str | None) -> None:
    """Insert one frame's operation and/or expect source into linecache.

    Either argument may be None or empty; missing/empty entries are skipped
    (no cache row written for that filename).

    Args:
        n: Frame number.
        operation: Operation source text (the original LLM string, NOT the
            bare-expression-rewritten version). When non-empty, registered
            under filename `<frame-{n}>`.
        expect: Expect source text. When non-empty, registered under
            filename `<frame-{n}-expect>`.

    Side effects:
        Mutates linecache.cache.
    """
    if operation:
        filename = f"<frame-{n}>"
        lines = operation.splitlines(keepends=True)
        linecache.cache[filename] = (len(operation), None, lines, filename)
    if expect:
        filename = f"<frame-{n}-expect>"
        lines = expect.splitlines(keepends=True)
        linecache.cache[filename] = (len(expect), None, lines, filename)


def reload_from_db(conn: sqlite3.Connection) -> int:
    """Scan the frame_content table and replay register() for every row.

    Called by Kernel on boot when a SQLite frame_log is opened. After this
    runs, inspect.getsource() works on cloudpickle-restored objects whose
    co_filename points at any frame previously written to this database.

    Args:
        conn: An open sqlite3.Connection to a frame_log database. The
            frame_content table must exist (caller is responsible for
            opening via open_db(); this function does not run DDL).

    Returns:
        Number of frame rows scanned (operation and expect counted as one row).
    """
    count = 0
    for n, op, exp in conn.execute(
        "SELECT n, pong_operation, pong_expect FROM frame_content"
    ):
        register(int(n), op, exp)
        count += 1
    return count
