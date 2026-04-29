"""End-to-end: drive main Cell through k frames, verify compaction Cell writes
a layer-1 entry into main's frame_log, verify main's next ping reads it."""

import sqlite3
from unittest.mock import patch

import pytest

from vessal.ark.shell.hull.cell.protocol import Pong, Action


def _canned_main_pong():
    return Pong(think="noop", action=Action(operation="x = 1", expect=""))


def _canned_compaction_pong():
    yaml_body = (
        "range:\n  n_start: 1\n  n_end: 4\n"
        "intent: stub compaction\n"
        "operations: [{n: 1, what: x=1}, {n: 2, what: x=1}, {n: 3, what: x=1}, {n: 4, what: x=1}]\n"
        "outcomes: []\nartifacts: []\nnotable: []\n"
    )
    op = (
        "view = compaction.read_pending()\n"
        "g = view.groups[0]\n"
        f"compaction.write_summary(layer=g.layer + 1, n_start=g.n_start, n_end=g.n_end, schema_version=1, body={yaml_body!r})\n"
    )
    return Pong(think="compact", action=Action(operation=op, expect=""))


def _write_minimal_project(path) -> None:
    from pathlib import Path
    p = Path(path)
    (p / "hull.toml").write_text(
        '[agent]\nname = "test"\n[cell]\nmax_frames = 20\n[hull]\nskills = []\nskill_paths = []\n',
        encoding="utf-8",
    )
    (p / ".env").write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")


def test_layer1_entry_lands_after_k_main_frames(tmp_path):
    from vessal.ark.shell.hull import Hull
    from vessal.ark.shell.hull._compaction_trigger import should_compact

    _write_minimal_project(tmp_path)
    hull = Hull(project_dir=str(tmp_path))

    main_step_return = (_canned_main_pong(), {})
    compaction_step_return = (_canned_compaction_pong(), {})

    with patch.object(hull._main_cell._core, "step", return_value=main_step_return), \
         patch.object(hull._compaction_cell._core, "step", return_value=compaction_step_return):
        for _ in range(5):  # 5 main frames > k=4 → trigger fires
            hull._main_cell.step()
            if should_compact(hull._main_db_path):
                hull._compaction_cell.step()

    # Verify a layer=1 entry covering n=1..4 exists in main's db
    conn = sqlite3.connect(hull._main_db_path)
    try:
        rows = conn.execute("SELECT layer, n_start, n_end FROM entries WHERE layer=1").fetchall()
        body = conn.execute("SELECT body FROM summary_content WHERE layer=1").fetchone()
    finally:
        conn.close()

    assert rows == [(1, 1, 4)]
    assert "stub compaction" in body[0]
