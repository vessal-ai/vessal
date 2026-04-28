"""test_dependency_direction — spec 4.4/6.1: dependency direction validation.

Verifies ARK internal dependency direction and isolation between ARK and Skills.
"""
import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]  # tests/architecture/ -> repo root


def _resolve_relative_import(py_file: Path, level: int, module: str | None) -> str | None:
    """Resolve a relative import to an absolute module path.

    Args:
        py_file: Path to the .py file containing the import.
        level: Relative import level (from . = 1, from .. = 2, etc.).
        module: Module name from the relative import (may be None, e.g. from . import foo).
    Returns:
        Resolved absolute module path, or None if resolution fails.
    """
    try:
        # Compute the package path starting from src/
        parts = py_file.parts
        src_idx = next(i for i, p in enumerate(parts) if p == "src")
        # Get the package path containing the current file (strip src and filename)
        pkg_parts = list(parts[src_idx + 1: -1])  # e.g. ["vessal", "ark", "hull"]
        # Walk up level-1 levels (level=1 means current package, level=2 means parent)
        if level > 1:
            pkg_parts = pkg_parts[:-(level - 1)] if len(pkg_parts) >= level - 1 else []
        base = ".".join(pkg_parts)
        if module:
            return f"{base}.{module}" if base else module
        return base or None
    except (StopIteration, IndexError):
        return None


def _scan_imports(source_dir: str, forbidden: list[str]) -> list[str]:
    """Scan all .py files in a directory for forbidden imports.

    Args:
        source_dir: Directory path to scan.
        forbidden: List of forbidden import prefixes.
    Returns:
        List of violations in format "file_path:line_number: imports module_name".
    """
    violations = []
    for py_file in Path(source_dir).rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        if "tests" in py_file.relative_to(source_dir).parts:
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                absolute_module = _resolve_relative_import(py_file, node.level, node.module)
                if absolute_module:
                    for f in forbidden:
                        if absolute_module.startswith(f):
                            violations.append(
                                f"{py_file}:{node.lineno}: relative imports {absolute_module}"
                            )
            elif isinstance(node, ast.ImportFrom) and node.module:
                for f in forbidden:
                    if node.module.startswith(f):
                        violations.append(
                            f"{py_file}:{node.lineno}: imports {node.module}"
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for f in forbidden:
                        if alias.name.startswith(f):
                            violations.append(
                                f"{py_file}:{node.lineno}: imports {alias.name}"
                            )
    return violations


def test_cell_imports_no_hull_or_shell():
    """Cell does not import Hull or Shell."""
    violations = _scan_imports(
        str(_REPO_ROOT / "src/vessal/ark/shell/hull/cell"),
        ["vessal.ark.shell.hull.hull", "vessal.ark.shell.hull.event_loop",
         "vessal.ark.shell.hull.skill_loader",
         "vessal.ark.shell.hull.skill",
         "vessal.ark.shell.server", "vessal.ark.shell.cli",
         "vessal.hull", "vessal.shell"],
    )
    assert violations == [], "Cell isolation violations:\n" + "\n".join(violations)


def test_cell_imports_no_util_logging():
    """Cell must not import ark.util.logging (TracerLike Protocol is the boundary)."""
    violations = _scan_imports(
        str(_REPO_ROOT / "src/vessal/ark/shell/hull/cell"),
        ["vessal.ark.util.logging"],
    )
    assert violations == [], "Cell must use TracerLike Protocol, not ark.util.logging directly:\n" + "\n".join(violations)


def test_hull_imports_no_shell():
    """Hull does not import Shell boundary code (server/cli)."""
    violations = _scan_imports(
        str(_REPO_ROOT / "src/vessal/ark/shell/hull"),
        ["vessal.ark.shell.server", "vessal.ark.shell.cli", "vessal.shell"],
    )
    assert violations == [], "Hull isolation violations:\n" + "\n".join(violations)


def test_ark_imports_no_skills():
    """ARK does not import Skills.

    Exception 1: Kernel imports vessal.skills.system (SystemSkill) and vessal.skills._base
    (BaseSkill) for the G["_system"] bootstrap and _signal_scan. This is the single
    intentional downward seam defined by spec §6.2: Kernel is the assembly point that
    binds the SystemSkill carrier to the execution engine.

    Exception 2: skill_cmds.py (CLI validator) imports vessal.skills._base to verify that
    user-provided Skills subclass BaseSkill. This is a validation seam: the CLI tool must
    know the canonical base class to enforce it.
    """
    _KERNEL_PY = str(_REPO_ROOT / "src/vessal/ark/shell/hull/cell/kernel/kernel.py")
    _SKILL_CMDS_PY = str(_REPO_ROOT / "src/vessal/ark/shell/cli/skill_cmds.py")
    _ALLOWED_FROM_KERNEL = {"vessal.skills.system", "vessal.skills._base"}
    _ALLOWED_FROM_CLI = {"vessal.skills._base"}
    violations = _scan_imports(
        str(_REPO_ROOT / "src/vessal/ark"),
        ["vessal.skills"],
    )
    filtered = [
        v for v in violations
        if not (
            v.startswith(_KERNEL_PY)
            and any(allowed in v for allowed in _ALLOWED_FROM_KERNEL)
        )
        and not (
            v.startswith(_SKILL_CMDS_PY)
            and any(allowed in v for allowed in _ALLOWED_FROM_CLI)
        )
    ]
    assert filtered == [], "ARK-Skills isolation violations:\n" + "\n".join(filtered)


def test_shell_does_not_access_hull_event_queue():
    """Shell boundary code should not directly access .event_queue.

    Shell boundary (server.py, cli.py) should inject events via hull.wake(),
    not directly manipulate hull.event_queue.put().
    Hull internal code is not subject to this constraint.
    """
    violations = []
    shell_dir = _REPO_ROOT / "src/vessal/ark/shell"
    hull_dir = shell_dir / "hull"
    for py_file in shell_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        # hull/ is a subsystem of shell/; internal use of event_queue is legitimate
        if py_file.is_relative_to(hull_dir):
            continue
        content = py_file.read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            if "event_queue" in line and not line.strip().startswith("#"):
                violations.append(f"{py_file}:{i}: accesses event_queue directly")
    assert violations == [], (
        "Shell should inject events via hull.wake(), not access event_queue directly:\n"
        + "\n".join(violations)
    )


def test_shell_does_not_access_hull_ns():
    """Shell boundary code should not directly access hull.ns.

    Shell boundary (server.py, cli.py) should use hull.status() / hull.frames() instead.
    Hull internal code is not subject to this constraint.
    """
    violations = []
    shell_dir = _REPO_ROOT / "src/vessal/ark/shell"
    hull_dir = shell_dir / "hull"
    for py_file in shell_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        # hull/ is a subsystem of shell/; internal access to ns is legitimate
        if py_file.is_relative_to(hull_dir):
            continue
        content = py_file.read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "hull.ns" in stripped or ".ns[" in stripped or ".ns.get(" in stripped:
                violations.append(f"{py_file}:{i}: accesses hull.ns directly")
    assert violations == [], (
        "Shell should query state via hull.status()/hull.frames():\n"
        + "\n".join(violations)
    )


def test_no_starlette_or_uvicorn_imports():
    """ARK code should not import starlette or uvicorn."""
    violations = _scan_imports(
        str(_REPO_ROOT / "src/vessal/ark"),
        ["starlette", "uvicorn"],
    )
    assert violations == [], "Starlette/Uvicorn leftover imports:\n" + "\n".join(violations)
