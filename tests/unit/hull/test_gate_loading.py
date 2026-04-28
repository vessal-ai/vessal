"""Test Hull loading custom gate functions from gates/ directory."""
import os
from pathlib import Path


def _write_minimal_project(path: Path):
    """Create minimal hull.toml + .env for testing."""
    (path / "hull.toml").write_text(
        '[agent]\nname = "test"\nlanguage = "en"\n'
        '[cell]\nmax_frames = 5\n'
        '[hull]\nskills = []\nskill_paths = []\n'
    )
    (path / ".env").write_text('OPENAI_API_KEY=test-key\n')


def test_hull_loads_action_gate_from_file(tmp_path):
    """Hull reads gates/action_gate.py and applies to cell."""
    _write_minimal_project(tmp_path)

    gates_dir = tmp_path / "gates"
    gates_dir.mkdir()
    (gates_dir / "action_gate.py").write_text(
        'def check(code: str) -> tuple[bool, str]:\n'
        '    if "dangerous" in code:\n'
        '        return False, "blocked dangerous"\n'
        '    return True, ""\n'
    )

    from vessal.ark.shell.hull.hull import Hull
    os.chdir(tmp_path)
    hull = Hull(str(tmp_path))

    result = hull._cell._action_gate.check('x = "dangerous"')
    assert not result.allowed


def test_hull_no_gates_dir_no_error(tmp_path):
    """Hull works fine without gates/ directory."""
    _write_minimal_project(tmp_path)

    from vessal.ark.shell.hull.hull import Hull
    os.chdir(tmp_path)
    Hull(str(tmp_path))  # Should not raise
