"""Kernel integration: db_path is optional; when set, frame_log is opened."""
from __future__ import annotations

from pathlib import Path

from vessal.ark.shell.hull.cell.kernel.kernel import Kernel


def test_kernel_db_path_optional_default_none() -> None:
    # Construct Kernel without db_path → must not raise, must not open any file.
    k = Kernel()
    assert k.frame_log is None     # public read-only attribute exposed by this PR


def test_kernel_db_path_sets_frame_log(tmp_path: Path) -> None:
    db_file = tmp_path / "fl.sqlite"
    k = Kernel(db_path=str(db_file))
    assert k.frame_log is not None
    assert db_file.exists()
