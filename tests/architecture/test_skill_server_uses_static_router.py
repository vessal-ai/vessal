"""test_skill_server_uses_static_router — forbid copy-pasted static-route boilerplate in Skill servers."""
from __future__ import annotations

import ast
from pathlib import Path


_SKILLS_DIR = Path(__file__).resolve().parents[2] / "src/vessal/skills"


def _module_globals(src: str) -> set[str]:
    tree = ast.parse(src)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_no_server_uses_static_cache_pattern():
    offenders: list[str] = []
    for pkg_dir in _SKILLS_DIR.iterdir():
        if not pkg_dir.is_dir():
            continue
        server_py = pkg_dir / "server.py"
        if not server_py.exists():
            continue
        src = server_py.read_text()
        globals_ = _module_globals(src)
        if "_static_cache" in globals_ and "_make_static_handler" in src:
            offenders.append(str(server_py))
    assert not offenders, (
        f"server.py using legacy static-route boilerplate (use StaticRouter instead):\n"
        + "\n".join(offenders)
    )
