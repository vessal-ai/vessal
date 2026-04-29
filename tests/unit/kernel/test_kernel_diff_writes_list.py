"""kernel writes obs_diff_json as a JSON list, not a doubly-encoded string."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
from vessal.ark.shell.hull.cell.protocol import Action, Pong


def test_obs_diff_json_is_json_array(tmp_path: Path):
    db = tmp_path / "fl.sqlite"
    k = Kernel(boot_script="", db_path=str(db))
    k.ping(None, {"globals": k.G, "locals": k.L})

    pong = Pong(think="", action=Action(operation="x = 1", expect=""))
    k.ping(pong, {"globals": k.G, "locals": k.L})

    rows = sqlite3.connect(str(db)).execute(
        "SELECT n, obs_diff_json FROM frame_content ORDER BY n"
    ).fetchall()
    n2_diff_text = rows[-1][1]
    parsed = json.loads(n2_diff_text)
    assert isinstance(parsed, list)
    assert parsed == [{"op": "+", "name": "x", "type": "int"}]


def test_boot_frame_obs_diff_json_is_empty_list(tmp_path: Path):
    db = tmp_path / "fl.sqlite"
    Kernel(boot_script="", db_path=str(db))

    row = sqlite3.connect(str(db)).execute(
        "SELECT obs_diff_json FROM frame_content WHERE n = 1"
    ).fetchone()
    parsed = json.loads(row[0])
    assert parsed == []
