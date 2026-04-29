"""Verify Hull constructs both main and compaction Cells, and snapshot covers both."""
from __future__ import annotations

import os
from pathlib import Path


def _write_minimal_project(path: Path) -> None:
    (path / "hull.toml").write_text(
        '[agent]\nname = "test"\nlanguage = "en"\n'
        '[cell]\nmax_frames = 5\n'
        '[hull]\nskills = []\nskill_paths = []\n',
        encoding="utf-8",
    )
    (path / ".env").write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")


def test_hull_has_both_cells(tmp_path):
    _write_minimal_project(tmp_path)
    from vessal.ark.shell.hull import Hull

    os.chdir(tmp_path)
    hull = Hull(project_dir=str(tmp_path))
    assert hull._main_cell.cell_name == "main"
    assert hull._compaction_cell.cell_name == "compaction"
    assert hull._main_db_path.endswith("frame_log.sqlite")
    assert hull._compaction_cell.G["compaction"]._main_db_path == hull._main_db_path


def test_snapshot_writes_both_cells(tmp_path):
    _write_minimal_project(tmp_path)
    from vessal.ark.shell.hull import Hull

    os.chdir(tmp_path)
    hull = Hull(project_dir=str(tmp_path))
    hull.snapshot()

    main_snaps = list((tmp_path / "data" / "main" / "snapshots").glob("*.pkl"))
    comp_snaps = list((tmp_path / "data" / "compaction" / "snapshots").glob("*.pkl"))
    assert len(main_snaps) == 1
    assert len(comp_snaps) == 1
