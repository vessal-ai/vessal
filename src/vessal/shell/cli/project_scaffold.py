"""project_scaffold.py — Project scaffold writer for `vessal create`."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def write_project_scaffold(project_dir: Path, install_venv: bool = True) -> None:
    """Create a Vessal project scaffold at `project_dir`.

    Writes hull.toml, SOUL.md, pyproject.toml, .env.example, .gitignore,
    skills/ (flat, one dir per Skill), and gates/.
    Optionally installs the virtual environment via uv or venv+pip and writes
    a vessal_user_skills.pth into the venv site-packages.
    Raises FileExistsError if project_dir already exists.
    """
    if project_dir.exists():
        raise FileExistsError(f"{project_dir} already exists")
    project_dir.mkdir(parents=True)
    project_name = project_dir.name

    skills_dir = project_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    builtin_skills_src = Path(__file__).resolve().parent.parent.parent / "skills"
    copied: list[str] = []
    if builtin_skills_src.exists():
        for child in builtin_skills_src.iterdir():
            if not child.is_dir():
                continue
            if child.name.startswith("_") or child.name == "__pycache__":
                continue
            shutil.copytree(
                str(child),
                str(skills_dir / child.name),
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            copied.append(child.name)

    from vessal.shell.cli.skills_init_writer import write_initial
    write_initial(skills_dir, copied)

    _write_hull_toml(project_dir, project_name)
    _write_soul_md(project_dir, project_name)
    _write_pyproject(project_dir, project_name)
    _write_env_example(project_dir)
    _write_gitignore(project_dir)
    _write_gates(project_dir)
    _write_main_cell_data_dir(project_dir)
    _write_compaction_cell_data_dir(project_dir)

    if install_venv:
        _install_dependencies(project_dir)
        _write_user_skills_pth(project_dir)


def _write_hull_toml(project_dir: Path, project_name: str) -> None:
    (project_dir / "hull.toml").write_text(
        f'[agent]\n'
        f'name = "{project_name}"\n'
        f'language = "en"\n'
        f'\n'
        f'[cell]\n'
        f'max_frames = 100\n'
        f'# Context budget (token count), should match the model\'s actual window size\n'
        f'# context_budget = 128000\n'
        f'\n'
        f'[core]\n'
        f'timeout = 60\n'
        f'max_retries = 3\n'
        f'\n'
        f'[core.api_params]\n'
        f'# Passed through to chat.completions.create(); supports any model parameters\n'
        f'temperature = 0.7\n'
        f'max_tokens = 4096\n'
        f'# Model-specific parameters as needed:\n'
        f'# top_p = 0.9\n'
        f'# top_k = 40\n'
        f'\n'
        f'[hull]\n'
        f'skills = ["tasks", "pin", "chat", "heartbeat", "skill_manager"]\n'
        f'# compress_threshold = 50  # Context pressure signal threshold (default 50%, read by Memory skill)\n'
        f'\n'
        f'[cells.main]\n'
        f'# Per-Cell data directory; relative to project root.\n'
        f'# Hosts frame_log.sqlite (Kernel\'s durable frame archive).\n'
        f'data_dir = "data/main"\n'
        f'\n'
        f'[gates]\n'
        f'# Gate conditions (see docs)\n',
        encoding="utf-8",
    )


def _write_soul_md(project_dir: Path, project_name: str) -> None:
    (project_dir / "SOUL.md").write_text(
        f'# {project_name} Agent Identity\n'
        f'\n'
        f'## Role\n'
        f'You are a general-purpose assistant.\n'
        f'\n'
        f'## Behavioral Preferences\n'
        f'- Prefer Python standard library; avoid unnecessary dependencies\n'
        f'- Verify paths exist before operating on files\n'
        f'- When encountering errors, read the frame stream to diagnose the cause before deciding next steps\n'
        f'\n'
        f'## Accumulated Experience\n'
        f'(The Agent may append experience here during runtime; writing back persists across episodes)\n',
        encoding="utf-8",
    )


def _write_pyproject(project_dir: Path, project_name: str) -> None:
    (project_dir / "pyproject.toml").write_text(
        f'[project]\n'
        f'name = "{project_name}"\n'
        f'version = "0.1.0"\n'
        f'description = "Vessal Agent"\n'
        f'requires-python = ">=3.12"\n'
        f'dependencies = ["vessal"]\n',
        encoding="utf-8",
    )


def _write_env_example(project_dir: Path) -> None:
    (project_dir / ".env.example").write_text(
        "OPENAI_API_KEY=your-api-key-here\n"
        "OPENAI_BASE_URL=https://api.openai.com/v1\n"
        "OPENAI_MODEL=gpt-4o\n",
        encoding="utf-8",
    )


def _write_gitignore(project_dir: Path) -> None:
    (project_dir / ".gitignore").write_text(
        ".env\n"
        ".venv/\n"
        "snapshots/\n"
        "logs/\n"
        "__pycache__/\n"
        "data/*/frame_log.sqlite-*\n",
        encoding="utf-8",
    )


def _write_gates(project_dir: Path) -> None:
    gates_dir = project_dir / "gates"
    gates_dir.mkdir(exist_ok=True)

    (gates_dir / "action_gate.py").write_text(
        '"""action_gate.py — Custom action safety rules.\n'
        '\n'
        'Define check(code: str) -> tuple[bool, str] function.\n'
        'Return (True, "") to allow execution, (False, "reason") to deny.\n'
        'This file is optional — delete it to use default patterns from hull.toml [gates].\n'
        '"""\n'
        '\n'
        '\n'
        'def check(code: str) -> tuple[bool, str]:\n'
        '    # Example: forbid deletion of root directory\n'
        '    # if "shutil.rmtree" in code and ("/" == code or "~" in code):\n'
        '    #     return False, "deleting system directories is forbidden"\n'
        '    return True, ""\n',
        encoding="utf-8",
    )

    (gates_dir / "state_gate.py").write_text(
        '"""state_gate.py — Custom state validation rules.\n'
        '\n'
        'Define check(state: str) -> tuple[bool, str] function.\n'
        'Return (True, "") to allow sending, (False, "reason") to deny.\n'
        'This file is optional — delete it to use default patterns from hull.toml [gates].\n'
        '"""\n'
        '\n'
        '\n'
        'def check(state: str) -> tuple[bool, str]:\n'
        '    # Example: limit context length\n'
        '    # if len(state) > 500_000:\n'
        '    #     return False, "context is too long"\n'
        '    return True, ""\n',
        encoding="utf-8",
    )


def _write_main_cell_data_dir(project_dir: Path) -> None:
    main_data = project_dir / "data" / "main"
    main_data.mkdir(parents=True, exist_ok=True)
    (main_data / ".gitkeep").write_text(
        "# Placeholder so the directory is committed even when empty.\n"
        "# Kernel writes frame_log.sqlite here at runtime.\n",
        encoding="utf-8",
    )


def _write_compaction_cell_data_dir(project_dir: Path) -> None:
    compaction_data = project_dir / "data" / "compaction"
    compaction_data.mkdir(parents=True, exist_ok=True)
    (compaction_data / ".gitkeep").write_text(
        "# Placeholder so the directory is committed even when empty.\n"
        "# Kernel writes compaction snapshots here at runtime.\n",
        encoding="utf-8",
    )


def _install_dependencies(project_dir: Path) -> None:
    if shutil.which("uv"):
        subprocess.run(["uv", "sync"], cwd=str(project_dir), check=True)
    else:
        venv_dir = project_dir / ".venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        bin_dir = "Scripts" if sys.platform == "win32" else "bin"
        venv_python = str(venv_dir / bin_dir / "python")
        subprocess.run([venv_python, "-m", "pip", "install", "vessal"], check=True)


def _write_user_skills_pth(project_dir: Path) -> None:
    """Write a .pth file into the project venv so `from skills.<name> import Skill` works.

    Idempotent: overwrites any existing file. Silently no-ops if the venv is missing.
    """
    venv = project_dir / ".venv"
    if not venv.is_dir():
        return
    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    venv_python = venv / bin_dir / "python"
    if not venv_python.exists():
        return
    out = subprocess.check_output(
        [str(venv_python), "-c", "import site; print(site.getsitepackages()[0])"],
        text=True,
    ).strip()
    site_packages = Path(out)
    site_packages.mkdir(parents=True, exist_ok=True)
    pth = site_packages / "vessal_user_skills.pth"
    pth.write_text(str(project_dir.resolve()) + "\n", encoding="utf-8")
