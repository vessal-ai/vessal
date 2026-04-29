"""boot frame writes spec-§7.6-compliant field values."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from vessal.ark.shell.hull.cell.kernel.kernel import Kernel


def test_boot_frame_pong_expect_is_empty_string(tmp_path: Path):
    db = tmp_path / "fl.sqlite"
    Kernel(boot_script="", db_path=str(db))
    row = sqlite3.connect(str(db)).execute(
        "SELECT pong_expect FROM frame_content WHERE n = 1"
    ).fetchone()
    assert row[0] == ""


def test_boot_frame_verdict_value_is_null(tmp_path: Path):
    db = tmp_path / "fl.sqlite"
    Kernel(boot_script="", db_path=str(db))
    row = sqlite3.connect(str(db)).execute(
        "SELECT verdict_value FROM frame_content WHERE n = 1"
    ).fetchone()
    assert row[0] is None


def test_boot_frame_obs_diff_json_is_empty_list_on_cold_start(tmp_path: Path):
    import json
    db = tmp_path / "fl.sqlite"
    Kernel(boot_script="", db_path=str(db))
    row = sqlite3.connect(str(db)).execute(
        "SELECT obs_diff_json FROM frame_content WHERE n = 1"
    ).fetchone()
    assert json.loads(row[0]) == []
