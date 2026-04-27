"""project_scaffold.py — Project scaffold writer for `vessal create`."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def write_project_scaffold(project_dir: Path, install_venv: bool = True) -> None:
    """Create a Vessal project scaffold at `project_dir`.

    Writes hull.toml, SOUL.md, pyproject.toml, .env.example, .gitignore,
    skills/{bundled,hub,local}/ with an example skill, and gates/.
    Optionally installs the virtual environment via uv or venv+pip.
    Raises FileExistsError if project_dir already exists.
    """
    if project_dir.exists():
        raise FileExistsError(f"{project_dir} already exists")
    project_dir.mkdir(parents=True)
    project_name = project_dir.name

    bundled_dir = project_dir / "skills" / "bundled"
    hub_dir = project_dir / "skills" / "hub"
    local_dir = project_dir / "skills" / "local"

    builtin_skills_src = Path(__file__).resolve().parent.parent.parent.parent / "skills"
    if builtin_skills_src.exists():
        # ui, search, audio, vision are distributed via SkillHub — not bundled
        shutil.copytree(
            str(builtin_skills_src),
            str(bundled_dir),
            ignore=shutil.ignore_patterns("__pycache__", "ui", "search", "audio", "vision"),
        )
    else:
        bundled_dir.mkdir(parents=True)

    hub_dir.mkdir(parents=True, exist_ok=True)
    local_dir.mkdir(parents=True, exist_ok=True)

    _write_hull_toml(project_dir, project_name)
    _write_soul_md(project_dir, project_name)
    _write_pyproject(project_dir, project_name)
    _write_env_example(project_dir)
    _write_gitignore(project_dir)
    _write_example_skill(local_dir)
    _write_gates(project_dir)
    _write_main_cell_data_dir(project_dir)

    if install_venv:
        _install_dependencies(project_dir)


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
        f'# error_buffer_cap = 200     # Maximum error records in ns["_errors"] (ring buffer)\n'
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
        f'skills = ["tasks", "pin", "chat", "heartbeat", "skills"]\n'
        f'skill_paths = ["skills/bundled", "skills/hub", "skills/local"]\n'
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


def _write_example_skill(local_dir: Path) -> None:
    example_dir = local_dir / "example"
    example_dir.mkdir()

    (example_dir / "__init__.py").write_text(
        '"""Example toolkit\n'
        '\n'
        'Provides basic text processing and math utilities, demonstrating Skill package conventions.\n'
        '"""\n'
        '\n'
        '__all__ = ["word_count", "reverse_text", "add", "multiply"]\n'
        '\n'
        '\n'
        'def word_count(text: str) -> int:\n'
        '    """Count the number of words in text.\n'
        '\n'
        '    text: input string to count words in\n'
        '    returns: number of words (split by whitespace)\n'
        '    """\n'
        '    return len(text.split())\n'
        '\n'
        '\n'
        'def reverse_text(text: str) -> str:\n'
        '    """Reverse a string.\n'
        '\n'
        '    text: string to reverse\n'
        '    returns: reversed string\n'
        '    """\n'
        '    return text[::-1]\n'
        '\n'
        '\n'
        'def add(a: float, b: float) -> float:\n'
        '    """Return the sum of two numbers.\n'
        '\n'
        '    a: first number\n'
        '    b: second number\n'
        '    returns: a + b\n'
        '    """\n'
        '    return a + b\n'
        '\n'
        '\n'
        'def multiply(a: float, b: float) -> float:\n'
        '    """Return the product of two numbers.\n'
        '\n'
        '    a: first number\n'
        '    b: second number\n'
        '    returns: a * b\n'
        '    """\n'
        '    return a * b\n',
        encoding="utf-8",
    )

    (example_dir / "SKILL.md").write_text(
        '---\n'
        'name: example\n'
        'version: "1.0"\n'
        'description: "Example toolkit"\n'
        'tags: [example, demo]\n'
        'category: development\n'
        '---\n'
        '\n'
        '# example\n'
        '\n'
        'Example toolkit. Provides basic text processing and math utilities, demonstrating Skill package conventions.\n'
        'Load and call via example.word_count() etc.\n'
        '\n'
        '## API\n'
        '\n'
        '    example.word_count(text: str) -> int\n'
        '    example.reverse_text(text: str) -> str\n'
        '    example.add(a, b) -> number\n'
        '    example.multiply(a, b) -> number\n',
        encoding="utf-8",
    )

    (example_dir / "requirements.txt").write_text(
        "# Declare Python package dependencies for this Skill, one per line\n"
        "# e.g.: requests>=2.28\n",
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


def _install_dependencies(project_dir: Path) -> None:
    if shutil.which("uv"):
        subprocess.run(["uv", "sync"], cwd=str(project_dir), check=True)
    else:
        venv_dir = project_dir / ".venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        bin_dir = "Scripts" if sys.platform == "win32" else "bin"
        venv_python = str(venv_dir / bin_dir / "python")
        subprocess.run([venv_python, "-m", "pip", "install", "vessal"], check=True)
