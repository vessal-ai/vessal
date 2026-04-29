"""Every retired L key has zero source-file references — no writers, no readers."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"

DEAD_KEYS = [
    "_context_pct",
    "_budget_total",
    "_context_budget",
    "_token_budget",
    "_frame_type",
    "_render_config",
    "_dropped_frame_count",
]


def test_no_source_file_references_dead_l_keys() -> None:
    for key in DEAD_KEYS:
        pattern = re.compile(rf'["\']{re.escape(key)}["\']')
        offenders: list[str] = []
        for path in SRC.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if pattern.search(text):
                offenders.append(str(path.relative_to(REPO_ROOT)))
        assert not offenders, (
            f"Dead L key {key!r} still referenced in: {offenders}."
        )


def test_no_source_file_references_sleeping_and_errors_keys() -> None:
    for key in ["_errors", "_error_buffer_cap", "_sleeping", "_next_wake"]:
        pattern = re.compile(rf'["\']{re.escape(key)}["\']')
        offenders: list[str] = []
        for path in SRC.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if pattern.search(text):
                offenders.append(str(path.relative_to(REPO_ROOT)))
        assert not offenders, (
            f"Dead L key {key!r} still referenced in: {offenders}."
        )


def test_kernel_has_no_sleep_method() -> None:
    from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
    k = Kernel(boot_script="")
    assert not hasattr(k, "sleep")
    assert "sleep" not in k.L


def test_kernel_l_init_only_seeds_frame_and_signals() -> None:
    from vessal.ark.shell.hull.cell.kernel.kernel import Kernel
    k = Kernel(boot_script="")
    assert set(k.L.keys()) == {"_frame", "signals"}
