"""Verify that compaction Cell failure does not propagate to the main Cell."""

from unittest.mock import patch

from vessal.cell.protocol import Pong, Action


def _good_main_pong():
    return Pong(think="ok", action=Action(operation="x = 1", expect=""))


def _write_minimal_project(path) -> None:
    from pathlib import Path
    p = Path(path)
    (p / "hull.toml").write_text(
        '[agent]\nname = "test"\n[cell]\nmax_frames = 20\n[hull]\nskills = []\n',
        encoding="utf-8",
    )
    (p / ".env").write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")


def test_main_cell_keeps_stepping_when_compaction_raises(tmp_path):
    import sqlite3
    from vessal.hull import Hull
    from vessal.hull._compaction_trigger import should_compact

    _write_minimal_project(tmp_path)
    hull = Hull(project_dir=str(tmp_path))

    main_step_return = (_good_main_pong(), {})

    with patch.object(hull._main_cell._core, "step", return_value=main_step_return):
        for _ in range(8):  # well over k frames
            result = hull._main_cell.step()
            assert result.protocol_error is None
            if should_compact(hull._main_db_path):
                # Compaction step is allowed to raise; catch it here (as EventLoop would)
                try:
                    hull._compaction_cell.step()
                except Exception:
                    pass

    # Main Cell completed 8 frames + 1 boot frame → 9 layer-0 entries
    conn = sqlite3.connect(hull._main_db_path)
    try:
        (count,) = conn.execute("SELECT COUNT(*) FROM entries WHERE layer=0").fetchone()
    finally:
        conn.close()
    assert count == 9
