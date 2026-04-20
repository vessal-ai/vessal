"""test_hull_no_shell_import.py — forbid any shell/ file importing shell.hub (which now lives under hull.hub).

After the 2026-04-20 Shell/Hull layering refactor (P1), `hub/` physically lives
under `hull/hub/`. This test prevents regression: any reappearance of the old
`from vessal.ark.shell.hub` path under the shell/ subtree is a layering violation.
"""
from __future__ import annotations

import re
from pathlib import Path

_SHELL_ROOT = Path(__file__).resolve().parents[2] / "src" / "vessal" / "ark" / "shell"
_FORBIDDEN = re.compile(r"\bvessal\.ark\.shell\.hub\b")


def test_shell_does_not_import_retired_hub_path() -> None:
    """No file under shell/ may import the retired shell.hub path."""
    offenders = []
    for py in _SHELL_ROOT.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        text = py.read_text(encoding="utf-8")
        if _FORBIDDEN.search(text):
            offenders.append(str(py.relative_to(_SHELL_ROOT.parents[3])))
    assert not offenders, (
        "shell.hub has been moved under shell.hull.hub — update these imports:\n  "
        + "\n  ".join(offenders)
    )
