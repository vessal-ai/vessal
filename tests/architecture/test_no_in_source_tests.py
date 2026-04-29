"""Architecture invariant: tests live under repo-root tests/, never under src/."""
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_no_tests_dir_under_src() -> None:
    src = REPO_ROOT / "src"
    offenders = [p for p in src.rglob("tests") if p.is_dir()]
    assert not offenders, (
        "No 'tests/' directory may live under src/. "
        f"Move these to repo-root tests/: {[str(p) for p in offenders]}"
    )


def test_no_test_files_under_src() -> None:
    src = REPO_ROOT / "src"
    offenders = [p for p in src.rglob("test_*.py") if p.is_file()]
    assert not offenders, (
        "No test_*.py files may live under src/. "
        f"Move these to repo-root tests/: {[str(p) for p in offenders]}"
    )
