"""PR 6: every L key abandoned by spec is gone — no writers, no readers."""
from __future__ import annotations

import re
from pathlib import Path

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
            f"Dead L key {key!r} still referenced in: {offenders}. "
            "PR 6 deletes all writers and readers."
        )


def test_kernel_l_init_seeds_minimal_keys() -> None:
    from vessal.ark.shell.hull.cell.kernel.kernel import Kernel

    k = Kernel(boot_script="")
    forbidden = {
        "_context_pct", "_budget_total", "_context_budget", "_token_budget",
        "_frame_type", "_render_config", "_dropped_frame_count",
    }
    found = set(k.L.keys()) & forbidden
    assert not found, (
        f"L init must not seed dead keys, but found: {found}"
    )
