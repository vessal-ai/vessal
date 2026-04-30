"""Unit tests for Compaction — userspace SQLite writer for layer-≥1 entries."""

import pytest


def test_init_stores_main_db_path(tmp_path):
    from vessal.skills.compaction._skill import Compaction

    db = tmp_path / "main_frame_log.sqlite"
    db.touch()
    skill = Compaction(main_db_path=str(db))

    assert skill._main_db_path == str(db)
    assert skill.signal == {}


def test_init_prints_self_introduction(tmp_path, capsys):
    from vessal.skills.compaction._skill import Compaction

    db = tmp_path / "main.sqlite"
    db.touch()
    Compaction(main_db_path=str(db))

    captured = capsys.readouterr()
    assert "Compaction" in captured.out
    assert str(db) in captured.out


@pytest.fixture
def main_db(tmp_path):
    """Create a fresh frame_log SQLite using the production schema."""
    from vessal.ark.shell.hull.cell.kernel.frame_log.schema import open_db
    path = tmp_path / "main_frame_log.sqlite"
    conn = open_db(str(path))
    conn.close()
    return str(path)


def test_write_summary_inserts_entries_and_summary_atomically(main_db):
    import sqlite3
    from vessal.skills.compaction._skill import Compaction

    skill = Compaction(main_db_path=main_db)
    skill.write_summary(
        layer=1, n_start=1, n_end=4, schema_version=1,
        body="range:\n  n_start: 1\n  n_end: 4\nintent: stub\n",
    )

    conn = sqlite3.connect(main_db)
    try:
        entries = conn.execute(
            "SELECT layer, n_start, n_end FROM entries WHERE layer=1"
        ).fetchall()
        summaries = conn.execute(
            "SELECT layer, n_start, schema_version, body FROM summary_content WHERE layer=1"
        ).fetchall()
    finally:
        conn.close()

    assert entries == [(1, 1, 4)]
    assert len(summaries) == 1
    assert summaries[0][:3] == (1, 1, 1)
    assert "intent: stub" in summaries[0][3]


def test_write_summary_rolls_back_on_pk_conflict(main_db):
    import sqlite3
    from vessal.skills.compaction._skill import Compaction

    skill = Compaction(main_db_path=main_db)
    skill.write_summary(layer=1, n_start=1, n_end=4, schema_version=1, body="first")

    with pytest.raises(sqlite3.IntegrityError):
        skill.write_summary(layer=1, n_start=1, n_end=4, schema_version=1, body="dup")

    conn = sqlite3.connect(main_db)
    try:
        rows = conn.execute("SELECT body FROM summary_content WHERE layer=1").fetchall()
    finally:
        conn.close()
    assert rows == [("first",)]


def test_read_pending_returns_no_groups_when_below_k(main_db):
    import sqlite3
    from vessal.skills.compaction._skill import Compaction

    conn = sqlite3.connect(main_db)
    try:
        for n in range(1, 4):  # 3 frames < k=4
            conn.execute("INSERT INTO entries(layer, n_start, n_end) VALUES (0, ?, ?)", (n, n))
            conn.execute(
                "INSERT INTO frame_content(n, pong_think, pong_operation, pong_expect, "
                "obs_stdout, obs_stderr, obs_diff_json, obs_error_id, verdict_value) "
                "VALUES (?, '', '', '', '', '', '[]', NULL, NULL)",
                (n,),
            )
        conn.commit()
    finally:
        conn.close()

    skill = Compaction(main_db_path=main_db)
    view = skill.read_pending()

    assert view.groups == []


def test_read_pending_returns_one_group_at_k(main_db):
    import sqlite3
    from vessal.skills.compaction._skill import Compaction

    conn = sqlite3.connect(main_db)
    try:
        for n in range(1, 5):  # 4 frames == k
            conn.execute("INSERT INTO entries(layer, n_start, n_end) VALUES (0, ?, ?)", (n, n))
            conn.execute(
                "INSERT INTO frame_content(n, pong_think, pong_operation, pong_expect, "
                "obs_stdout, obs_stderr, obs_diff_json, obs_error_id, verdict_value) "
                "VALUES (?, ?, ?, '', ?, '', '[]', NULL, NULL)",
                (n, f"think{n}", f"op{n}", f"out{n}"),
            )
        conn.commit()
    finally:
        conn.close()

    skill = Compaction(main_db_path=main_db)
    view = skill.read_pending()

    assert len(view.groups) == 1
    g = view.groups[0]
    assert g.layer == 0
    assert g.n_start == 1
    assert g.n_end == 4
    assert len(g.items) == 4
    assert g.items[0]["n"] == 1
    assert g.items[0]["operation"] == "op1"


def test_read_pending_skips_layers_already_covered(main_db):
    import sqlite3
    from vessal.skills.compaction._skill import Compaction

    conn = sqlite3.connect(main_db)
    try:
        for n in range(1, 5):
            conn.execute("INSERT INTO entries(layer, n_start, n_end) VALUES (0, ?, ?)", (n, n))
            conn.execute(
                "INSERT INTO frame_content(n, pong_think, pong_operation, pong_expect, "
                "obs_stdout, obs_stderr, obs_diff_json, obs_error_id, verdict_value) "
                "VALUES (?, '', '', '', '', '', '[]', NULL, NULL)",
                (n,),
            )
        # Insert a covering layer-1 entry over n=1..4
        conn.execute("INSERT INTO entries(layer, n_start, n_end) VALUES (1, 1, 4)")
        conn.execute(
            "INSERT INTO summary_content(layer, n_start, schema_version, body) VALUES (1, 1, 1, 'stub')"
        )
        conn.commit()
    finally:
        conn.close()

    skill = Compaction(main_db_path=main_db)
    view = skill.read_pending()
    # layer 0 has no uncovered entries; layer 1 has 1 entry < k; nothing pending
    assert view.groups == []


def test_system_prompt_loads_and_is_nonempty():
    from vessal.ark.util.compaction_prompts import COMPACTION_SYSTEM_PROMPT

    assert isinstance(COMPACTION_SYSTEM_PROMPT, str)
    assert "compaction" in COMPACTION_SYSTEM_PROMPT.lower()
    assert "read_pending" in COMPACTION_SYSTEM_PROMPT
    assert "write_summary" in COMPACTION_SYSTEM_PROMPT
    assert "schema_version" in COMPACTION_SYSTEM_PROMPT
