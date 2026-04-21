"""test_no_duplicate_http_handlers.py — forbid duplicate do_GET/do_POST in runtime/.

Before the 2026-04-20 Shell/Hull layering refactor (P4), both
`hull_runner._HullHandler` and `container/entry._ContainerHandler` defined
`do_GET` and `do_POST` independently (~80 lines of near-identical code).
After P4 a single `HullHttpHandlerBase` owns these methods; subclasses may
only override `do_GET` (for carrier-specific bypasses like /healthz).
This test prevents regression: any new concrete handler class under runtime/
that defines `do_POST` directly (rather than inheriting it) breaks the rule.
"""
from __future__ import annotations

import ast
from pathlib import Path

_RUNTIME_DIR = Path(__file__).resolve().parents[2] / "src" / "vessal" / "ark" / "shell" / "runtime"


def _concrete_handlers(root: Path) -> list[tuple[str, str, set[str]]]:
    """Return (file, class_name, defined_method_names) for every handler class."""
    out: list[tuple[str, str, set[str]]] = []
    if not root.exists():
        return out
    for py in root.rglob("*.py"):
        if "__pycache__" in py.parts or py.parent.name == "tests":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                base_names = {b.id for b in node.bases if isinstance(b, ast.Name)} | {
                    b.attr for b in node.bases if isinstance(b, ast.Attribute)
                }
                if "HullHttpHandlerBase" in base_names or "BaseHTTPRequestHandler" in base_names:
                    methods = {m.name for m in node.body if isinstance(m, ast.FunctionDef)}
                    out.append((str(py.name), node.name, methods))
    return out


def test_do_post_defined_only_in_base() -> None:
    """No concrete carrier handler may override do_POST."""
    violators = [
        (f, c) for (f, c, methods) in _concrete_handlers(_RUNTIME_DIR)
        if c != "HullHttpHandlerBase" and "do_POST" in methods
    ]
    assert not violators, (
        "do_POST must be inherited from HullHttpHandlerBase, not redefined:\n  "
        + "\n  ".join(f"{f}::{c}" for f, c in violators)
    )


def test_read_json_defined_only_in_base() -> None:
    violators = [
        (f, c) for (f, c, methods) in _concrete_handlers(_RUNTIME_DIR)
        if c != "HullHttpHandlerBase" and "_read_json" in methods
    ]
    assert not violators, (
        "_read_json must be inherited from HullHttpHandlerBase, not redefined:\n  "
        + "\n  ".join(f"{f}::{c}" for f, c in violators)
    )
