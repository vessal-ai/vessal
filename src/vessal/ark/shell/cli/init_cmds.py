"""init_cmds.py — vessal init CLI command implementation."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _cmd_init(args: argparse.Namespace) -> None:
    """Execute vessal init command.

    Creates project directory, generates hull.toml, SOUL.md, pyproject.toml, .env.example,
    .gitignore, skills/example/ example Skill package, and sets up the virtual environment.
    Detects uv (runs uv sync) or falls back to python -m venv + pip install vessal.
    Pass --no-venv to skip virtual environment creation.
    Exits with error if directory already exists.
    """
    project_dir = Path(args.name)
    if project_dir.exists():
        print(f"Error: directory {args.name} already exists.", file=sys.stderr)
        sys.exit(1)

    project_dir.mkdir(parents=True)

    # Three-directory skill layout: bundled (preinstalled), hub (SkillHub downloads), local (user-developed)
    import shutil
    bundled_dir = project_dir / "skills" / "bundled"
    hub_dir = project_dir / "skills" / "hub"
    local_dir = project_dir / "skills" / "local"

    builtin_skills_src = Path(__file__).resolve().parent.parent.parent.parent / "skills"
    if builtin_skills_src.exists():
        shutil.copytree(str(builtin_skills_src), str(bundled_dir),
                        ignore=shutil.ignore_patterns("__pycache__"))
    else:
        bundled_dir.mkdir(parents=True)

    hub_dir.mkdir(parents=True, exist_ok=True)
    local_dir.mkdir(parents=True, exist_ok=True)

    # hull.toml
    (project_dir / "hull.toml").write_text(
        f"""[agent]
name = "{args.name}"
language = "en"

[cell]
max_frames = 100
# Context budget (token count), should match the model's actual window size
# context_budget = 128000

[core]
timeout = 60
max_retries = 3

[core.api_params]
# Passed through to chat.completions.create(); supports any model parameters
temperature = 0.7
max_tokens = 4096
# Model-specific parameters as needed:
# top_p = 0.9
# top_k = 40

[hull]
skills = ["tasks", "pin", "chat", "heartbeat", "skills"]
skill_paths = ["skills/bundled", "skills/hub", "skills/local"]
# compress_threshold = 50  # Context pressure signal threshold (default 50%, read by Memory skill)

[gates]
# Gate conditions (see docs)
""",
        encoding="utf-8",
    )

    # SOUL.md — Agent identity definition
    # Loaded automatically by Hull at startup into _system_prompt variable,
    # presented to the LLM as a system prompt section.
    # The Agent can modify SOUL.md during runtime to accumulate experience;
    # writing it back persists across episodes.
    (project_dir / "SOUL.md").write_text(
        f"""\
# {args.name} Agent Identity

## Role
You are a general-purpose assistant.

## Behavioral Preferences
- Prefer Python standard library; avoid unnecessary dependencies
- Verify paths exist before operating on files
- When encountering errors, read the frame stream to diagnose the cause before deciding next steps

## Accumulated Experience
(The Agent may append experience here during runtime; writing back persists across episodes)
""",
        encoding="utf-8",
    )

    # pyproject.toml
    (project_dir / "pyproject.toml").write_text(
        f"""[project]
name = "{args.name}"
version = "0.1.0"
description = "Vessal Agent"
requires-python = ">=3.12"
dependencies = ["vessal"]
""",
        encoding="utf-8",
    )

    # .env.example
    (project_dir / ".env.example").write_text(
        "OPENAI_API_KEY=your-api-key-here\n"
        "OPENAI_BASE_URL=https://api.openai.com/v1\n"
        "OPENAI_MODEL=gpt-4o\n",
        encoding="utf-8",
    )

    # .gitignore
    (project_dir / ".gitignore").write_text(
        """.env
.venv/
snapshots/
logs/
__pycache__/
""",
        encoding="utf-8",
    )

    # skills/local/example/ — example Skill package
    # Demonstrates Skill development conventions: module docstrings, __all__, function docstrings, type annotations
    example_dir = local_dir / "example"
    example_dir.mkdir()

    (example_dir / "__init__.py").write_text(
        '''\
"""Example toolkit

Provides basic text processing and math utilities, demonstrating Skill package conventions.
"""

__all__ = ["word_count", "reverse_text", "add", "multiply"]


def word_count(text: str) -> int:
    """Count the number of words in text.

    text: input string to count words in
    returns: number of words (split by whitespace)
    """
    return len(text.split())


def reverse_text(text: str) -> str:
    """Reverse a string.

    text: string to reverse
    returns: reversed string
    """
    return text[::-1]


def add(a: float, b: float) -> float:
    """Return the sum of two numbers.

    a: first number
    b: second number
    returns: a + b
    """
    return a + b


def multiply(a: float, b: float) -> float:
    """Return the product of two numbers.

    a: first number
    b: second number
    returns: a * b
    """
    return a * b
''',
        encoding="utf-8",
    )

    # skills/example/SKILL.md — usage guide example
    (example_dir / "SKILL.md").write_text(
        """\
---
name: example
version: "1.0"
description: "Example toolkit"
tags: [example, demo]
category: development
---

# example

Example toolkit. Provides basic text processing and math utilities, demonstrating Skill package conventions.
Load and call via example.word_count() etc.

## API

    example.word_count(text: str) -> int
    example.reverse_text(text: str) -> str
    example.add(a, b) -> number
    example.multiply(a, b) -> number
""",
        encoding="utf-8",
    )

    # requirements.txt (example: empty file, showing where to declare dependencies)
    (example_dir / "requirements.txt").write_text(
        "# Declare Python package dependencies for this Skill, one per line\n# e.g.: requests>=2.28\n",
        encoding="utf-8",
    )

    # gates/ — custom gate rule files
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

    # Create virtual environment and install dependencies
    import subprocess as sp
    if not getattr(args, "no_venv", False):
        import shutil as _shutil
        if _shutil.which("uv"):
            sp.run(["uv", "sync"], cwd=str(project_dir), check=True)
        else:
            venv_dir = project_dir / ".venv"
            sp.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            bin_dir = "Scripts" if sys.platform == "win32" else "bin"
            venv_python = str(venv_dir / bin_dir / "python")
            sp.run([venv_python, "-m", "pip", "install", "vessal"], check=True)

    print(f"\nDone! Project '{args.name}' is ready.\n")
    print(f"  cd {args.name}")
    print(f"  cp .env.example .env")
    print(f"  # Fill in OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL")
    print()
    print(f"  vessal start")
