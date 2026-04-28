"""test_cell_dependency_tree.py — Cell is a leaf. No outward dependencies.

Asserts C14 invariant from console/1-active/20260421-cell-architecture-review.md.
"""
from __future__ import annotations
import ast
from pathlib import Path

CELL_ROOT = Path(__file__).resolve().parents[3] / "src/vessal/ark/shell/hull/cell"

FORBIDDEN_IMPORTS = {
    "vessal.ark.util.logging",      # A1 — use TracerLike Protocol instead
    "vessal.ark.shell.hull",         # A2 — Cell must not know Hull modules outside cell/
}

# Prefixes that are allowed even though they start with a forbidden prefix.
# Cell's own sub-packages live under vessal.ark.shell.hull.cell and are permitted.
ALLOWED_PREFIXES = {
    "vessal.ark.shell.hull.cell",
}

FORBIDDEN_PATTERNS = {
    "Core._DEFAULT_API_PARAMS",      # A3
    "fs._hot[",                       # D2
    "._rules.clear(",                 # D1
    '"_max_tokens"',                  # A3 — OpenAI vocab banned; use "_token_budget"
    "'_max_tokens'",                  # A3 — same, single-quoted form
}


def _iter_python_files(root: Path):
    for p in root.rglob("*.py"):
        if "tests" in p.parts:
            continue
        yield p


def _is_forbidden(module_name: str) -> bool:
    """Return True if module_name starts with a forbidden prefix and is not an allowed sub-package."""
    for allowed in ALLOWED_PREFIXES:
        if module_name.startswith(allowed):
            return False
    for forbidden in FORBIDDEN_IMPORTS:
        if module_name.startswith(forbidden):
            return True
    return False


def test_cell_does_not_import_forbidden_modules():
    offenders = []
    for path in _iter_python_files(CELL_ROOT):
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if _is_forbidden(node.module):
                    offenders.append(f"{path}: from {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden(alias.name):
                        offenders.append(f"{path}: import {alias.name}")
    assert offenders == [], "Cell imports forbidden modules:\n  " + "\n  ".join(offenders)


def test_cell_does_not_use_forbidden_patterns():
    offenders = []
    for path in _iter_python_files(CELL_ROOT):
        src = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in src:
                offenders.append(f"{path}: contains `{pattern}`")
    assert offenders == [], "Cell contains forbidden patterns:\n  " + "\n  ".join(offenders)


def test_cell_outside_kernel_does_not_import_sqlite3() -> None:
    """sqlite3 is a Kernel-frame_log internal. Cell-level code (cell.py, gate/, etc.)
    must not import it directly — frame persistence is Kernel's responsibility.
    """
    offenders = []
    for path in _iter_python_files(CELL_ROOT):
        # Kernel package may import sqlite3; skip it.
        if "kernel" in path.parts:
            continue
        src = path.read_text(encoding="utf-8")
        if not src.strip():
            continue
        tree = ast.parse(src, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "sqlite3":
                        offenders.append(f"{path}: import sqlite3")
            elif isinstance(node, ast.ImportFrom):
                if node.module == "sqlite3":
                    offenders.append(f"{path}: from sqlite3")
    assert offenders == [], "Cell (outside kernel/) imports sqlite3:\n  " + "\n  ".join(offenders)


def test_kernel_does_not_import_render_module():
    """Spec §1.4: Kernel does not stringify."""
    import os
    import importlib
    kernel_mod = importlib.import_module("vessal.ark.shell.hull.cell.kernel.kernel")
    kernel_dir = os.path.dirname(kernel_mod.__file__)
    forbidden = {"render", "frame_stream", "compression_parser"}
    for root, dirs, files in os.walk(kernel_dir):
        # Skip the frame_log/reader.py which is allowed (it reads, not renders)
        dirs[:] = [d for d in dirs if d != "frame_log"]
        for f in files:
            if not f.endswith(".py"):
                continue
            text = open(os.path.join(root, f)).read()
            for sym in forbidden:
                bad = f"from vessal.ark.shell.hull.cell.kernel.{sym}"
                assert bad not in text, f"{f} imports forbidden {sym}"


def test_kernel_does_not_compute_token_budget():
    """Spec §1.4: Kernel does not compute token budgets."""
    import inspect
    from vessal.ark.shell.hull.cell.kernel import kernel
    src = inspect.getsource(kernel)
    forbidden = ["estimate_tokens", "_context_budget", "_token_budget", "_budget_total", "_context_pct"]
    for sym in forbidden:
        assert sym not in src, f"kernel.py mentions forbidden symbol: {sym}"


def test_ping_state_protocol_is_dataclass():
    """Spec §4.8: State.frame_stream is FrameStream dataclass, signals is dict."""
    import dataclasses
    from vessal.ark.shell.hull.cell.protocol import State, FrameStream
    fields = {f.name: f.type for f in dataclasses.fields(State)}
    assert "frame_stream" in fields
    assert "signals" in fields
    # Verify the actual values (not just field names)
    state = State(frame_stream=FrameStream(entries=[]), signals={})
    assert isinstance(state.frame_stream, FrameStream)
    assert isinstance(state.signals, dict)
