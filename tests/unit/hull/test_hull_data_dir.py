"""test_hull_data_dir — Hull computes data_dir from hull.toml [cells.main] and wires Cell."""
from __future__ import annotations

import os
from pathlib import Path


def _write_minimal_project(path: Path, *, cells_table: str = "") -> None:
    """Write the smallest hull.toml + .env that lets Hull(...) construct.

    cells_table: optional extra TOML appended (e.g., '[cells.main]\\ndata_dir="data/main"\\n').
    """
    (path / "hull.toml").write_text(
        '[agent]\nname = "test"\nlanguage = "en"\n'
        '[cell]\nmax_frames = 5\n'
        '[hull]\nskills = []\nskill_paths = []\n'
        + cells_table,
        encoding="utf-8",
    )
    (path / ".env").write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")


def test_hull_creates_default_data_dir_for_main_cell(tmp_path):
    """No [cells.main] in hull.toml → Hull defaults to project/data/main and creates it."""
    _write_minimal_project(tmp_path)

    from vessal.ark.shell.hull.hull import Hull
    os.chdir(tmp_path)
    hull = Hull(str(tmp_path))

    expected = tmp_path / "data" / "main"
    assert expected.is_dir(), f"Hull did not create {expected}"
    assert hull._cell._data_dir == str(expected)
    assert hull._cell.cell_name == "main"
    assert hull._cell._kernel.frame_log is not None
    assert (expected / "frame_log.sqlite").exists()


def test_hull_honors_explicit_cells_main_data_dir(tmp_path):
    """[cells.main] data_dir override resolves relative to project_dir."""
    cells_table = '[cells.main]\ndata_dir = "custom/cells/primary"\n'
    _write_minimal_project(tmp_path, cells_table=cells_table)

    from vessal.ark.shell.hull.hull import Hull
    os.chdir(tmp_path)
    hull = Hull(str(tmp_path))

    expected = tmp_path / "custom" / "cells" / "primary"
    assert expected.is_dir()
    assert hull._cell._data_dir == str(expected)
    assert (expected / "frame_log.sqlite").exists()


def test_hull_rejects_absolute_data_dir(tmp_path):
    """Absolute data_dir paths are rejected — keep all data inside project_dir."""
    cells_table = f'[cells.main]\ndata_dir = "{tmp_path / "outside"}"\n'
    _write_minimal_project(tmp_path, cells_table=cells_table)

    from vessal.ark.shell.hull.hull import Hull
    import pytest
    os.chdir(tmp_path)
    with pytest.raises(ValueError) as exc:
        Hull(str(tmp_path))
    assert "data_dir must be relative" in str(exc.value)
