"""test_hull_startup_no_skills_manager — Hull must not import SkillsManager nor pre-set 'skills' in ns."""
from __future__ import annotations

import ast
from pathlib import Path



HULL_INIT_MIXIN = Path(__file__).resolve().parents[1] / "hull_init_mixin.py"


def test_no_skills_manager_import():
    tree = ast.parse(HULL_INIT_MIXIN.read_text())
    imports = [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.Import, ast.ImportFrom))
    ]
    for n in imports:
        mod = getattr(n, "module", "") or ""
        names = [a.name for a in n.names]
        assert "skills_manager" not in mod, f"hull_init_mixin still imports {mod}"
        assert "SkillsManager" not in names, "hull_init_mixin still imports SkillsManager"


def test_hull_skills_absent_from_ns_when_not_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hull.toml").write_text(
        "[hull]\nskills = []\nskill_paths = []\n", encoding="utf-8"
    )
    from vessal.ark.shell.hull.hull import Hull
    hull = Hull(str(tmp_path))
    assert "skills" not in hull._cell.ns, \
        "'skills' should not be pre-injected; it must come from [hull].skills config"
