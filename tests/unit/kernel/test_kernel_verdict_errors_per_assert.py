"""kernel writes one errors row per failed expect assertion (spec §3.5.6 / §4.5)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
from vessal.ark.shell.hull.cell.protocol import Action, Pong


def test_runtime_error_per_assert_lays_down_one_errors_row_each(tmp_path: Path):
    db = tmp_path / "fl.sqlite"
    k = Kernel(boot_script="", db_path=str(db))
    k.ping(None, {"globals": k.G, "locals": k.L})

    pong = Pong(think="", action=Action(
        operation="x = 1",
        expect="assert undefined_a > 0\nassert undefined_b > 0",
    ))
    k.ping(pong, {"globals": k.G, "locals": k.L})

    err_rows = sqlite3.connect(str(db)).execute(
        "SELECT n_start, source, format_text FROM errors WHERE source='expect' ORDER BY id"
    ).fetchall()
    # Two undefined names → two NameErrors → two rows
    assert len(err_rows) == 2
    assert all(r[0] == 2 for r in err_rows)  # all on frame 2 (boot is n=1)
    assert all(r[1] == "expect" for r in err_rows)


def test_assertion_failed_does_not_lay_down_errors_row(tmp_path: Path):
    """assertion_failed is not a Python exception (spec §3.5.6) — no errors row."""
    db = tmp_path / "fl.sqlite"
    k = Kernel(boot_script="", db_path=str(db))
    k.ping(None, {"globals": k.G, "locals": k.L})

    pong = Pong(think="", action=Action(
        operation="x = 1",
        expect="assert x == 99",  # plain assertion failure, not exception
    ))
    k.ping(pong, {"globals": k.G, "locals": k.L})

    err_rows = sqlite3.connect(str(db)).execute(
        "SELECT id FROM errors WHERE source='expect'"
    ).fetchall()
    assert err_rows == []  # Verdict.failures has the message, errors table empty


def test_verdict_value_is_verdict_to_dict_json(tmp_path: Path):
    db = tmp_path / "fl.sqlite"
    k = Kernel(boot_script="", db_path=str(db))
    k.ping(None, {"globals": k.G, "locals": k.L})

    pong = Pong(think="", action=Action(
        operation="x = 1",
        expect="assert x == 1\nassert x == 99",
    ))
    k.ping(pong, {"globals": k.G, "locals": k.L})

    row = sqlite3.connect(str(db)).execute(
        "SELECT verdict_value FROM frame_content WHERE n=2"
    ).fetchone()
    parsed = json.loads(row[0])
    assert parsed["total"] == 2
    assert parsed["passed"] == 1
    assert len(parsed["failures"]) == 1
    assert parsed["failures"][0]["kind"] == "assertion_failed"
