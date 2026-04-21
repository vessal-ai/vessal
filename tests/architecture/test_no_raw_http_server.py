"""test_no_raw_http_server — D7 defense.

Production code must never construct ``http.server.HTTPServer`` or
``http.server.ThreadingHTTPServer`` directly. The only legitimate
construction site is ``src/vessal/ark/shell/http_server.py``, which wraps
them with the project's quiet-disconnect ``handle_error`` policy.

Tests under ``tests/`` are whitelisted — they use ``HTTPServer`` as fake
backends in controlled scenarios where client disconnects cannot happen.
"""
from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src" / "vessal"
_ALLOWED_FILE = _SRC_ROOT / "ark" / "shell" / "http_server.py"

_FORBIDDEN_NAMES = {"HTTPServer", "ThreadingHTTPServer"}


def _scan_file(py_file: Path) -> list[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Pattern A: http.server.HTTPServer(...)
        if (
            isinstance(func, ast.Attribute)
            and func.attr in _FORBIDDEN_NAMES
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "server"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "http"
        ):
            hits.append(f"{py_file}:{node.lineno}: http.server.{func.attr}(...)")
        # Pattern B: from http.server import HTTPServer; HTTPServer(...)
        elif isinstance(func, ast.Name) and func.id in _FORBIDDEN_NAMES:
            hits.append(f"{py_file}:{node.lineno}: {func.id}(...)  # raw import")
    return hits


def test_no_raw_http_server_in_production():
    allowed = _ALLOWED_FILE.resolve()
    violations: list[str] = []
    for py_file in _SRC_ROOT.rglob("*.py"):
        py_file = py_file.resolve()
        if "__pycache__" in str(py_file) or py_file == allowed:
            continue
        # Co-located test directories inside src/ are whitelisted — they use
        # HTTPServer as fake backends in controlled test scenarios.
        if "/tests/" in str(py_file):
            continue
        violations.extend(_scan_file(py_file))
    assert not violations, (
        "Production code must use vessal.ark.shell.http_server.Safe*HTTPServer "
        "instead of raw http.server.HTTPServer/ThreadingHTTPServer. "
        "Violations:\n  " + "\n  ".join(violations)
    )
