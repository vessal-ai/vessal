"""test_cell_data_dir — Cell threads data_dir to Kernel, opening frame_log under it."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from vessal.ark.shell.hull.cell import Cell


def _make_cell(**kwargs) -> Cell:
    """Construct Cell while stubbing the OpenAI client (no real network)."""
    with patch("vessal.ark.shell.hull.cell.core.core.openai.OpenAI"):
        return Cell(**kwargs)


def test_cell_with_data_dir_opens_frame_log(tmp_path):
    """Cell(data_dir=...) opens a SQLite frame_log at <data_dir>/frame_log.sqlite."""
    data_dir = tmp_path / "data" / "main"
    data_dir.mkdir(parents=True)

    cell = _make_cell(cell_name="main", data_dir=str(data_dir))

    assert cell._data_dir == str(data_dir)
    assert cell.cell_name == "main"
    assert cell._kernel.frame_log is not None
    assert (data_dir / "frame_log.sqlite").exists()


def test_cell_without_data_dir_has_no_frame_log():
    """Cell() without data_dir keeps Kernel.frame_log = None (back-compat)."""
    cell = _make_cell()
    assert cell._kernel.frame_log is None
    assert cell._data_dir is None
    assert cell.cell_name == "main"  # default name even when data_dir is absent


def test_cell_data_dir_must_already_exist(tmp_path):
    """Cell does not auto-create data_dir; Hull is responsible for mkdir.

    Cell does receive an absolute path that must exist — if it doesn't,
    sqlite3.connect will create the file (a stray sqlite at a missing parent
    raises). We assert Cell raises a clear FileNotFoundError pointing at the
    missing directory, rather than letting sqlite3 emit an opaque OperationalError.
    """
    missing = tmp_path / "does" / "not" / "exist"
    with pytest.raises(FileNotFoundError) as exc:
        _make_cell(cell_name="main", data_dir=str(missing))
    assert str(missing) in str(exc.value)
