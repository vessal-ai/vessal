"""create_wizard.py — interactive wizard invoked by `vessal create` or the TUI picker."""
from __future__ import annotations

from pathlib import Path

from vessal.ark.shell.errors import CliUserError


def validate_project_name(name: str, cwd: Path) -> str | None:
    """Return an error string if the name is unusable, else None.

    Rules:
      1. Non-empty after strip.
      2. The resolved path cwd/name must not already exist.
    """
    if not name.strip():
        return "Project name cannot be empty."
    target = cwd / name
    if target.exists():
        return f"{target} already exists. Pick another name."
    return None


DEFAULT_ANSWERS = {
    "name": "my-agent",
    "api_key": "",
    "base_url": "",
    "model": "",
    "dockerize": False,
}


def finalize_answers(user_answers: dict) -> dict:
    """Fill missing fields with defaults; validate."""
    merged = dict(DEFAULT_ANSWERS)
    merged.update({k: v for k, v in user_answers.items() if v is not None})
    if not merged["name"]:
        raise ValueError("name cannot be empty")
    return merged


def _build_env_content(api_key: str, base_url: str, model: str) -> str:
    """Render .env content with English placeholders for any empty field.

    All three fields are always emitted. Empty inputs produce a commented
    placeholder so the user can fill them in directly.
    """
    def _line(key: str, value: str, hint: str) -> str:
        if value:
            return f"{key}={value}"
        return f"{key}=  # {hint}"

    return (
        _line("OPENAI_API_KEY", api_key, "Your API key here") + "\n"
        + _line("OPENAI_BASE_URL", base_url, "e.g. https://api.openai.com/v1") + "\n"
        + _line("OPENAI_MODEL", model, "e.g. gpt-4o") + "\n"
    )


def run(cwd: Path | None = None) -> int:
    """Run the interactive new-project wizard.

    Returns exit code (0 = success, non-zero = user aborted).
    """
    from vessal.ark.shell.tui.inline_prompt import ask_text, ask_yes_no

    cwd = (cwd or Path.cwd()).resolve()
    answers: dict = {}

    print("Vessal project wizard (press Enter to accept defaults, Ctrl-C to cancel)")
    print()

    # 1. Project name
    answers["name"] = ask_text(
        "Project name",
        default=DEFAULT_ANSWERS["name"],
        validator=lambda value: validate_project_name(value, cwd),
    )

    # 2. LLM configuration (entire step may be skipped by pressing Enter through all three).
    print()
    print("LLM configuration (leave blank to skip; you can fill .env later):")
    answers["api_key"] = ask_text("  OPENAI_API_KEY", default="")
    answers["base_url"] = ask_text("  OPENAI_BASE_URL", default="")
    answers["model"] = ask_text("  OPENAI_MODEL", default="")

    # 3. Dockerize (kept from previous wizard — actually consumed downstream)
    print()
    answers["dockerize"] = ask_yes_no("Generate a Dockerfile?", default=False)

    finalized = finalize_answers(answers)
    _scaffold(cwd / finalized["name"], finalized)
    print()
    print(f"Project created at {cwd / finalized['name']}")
    return 0


def _scaffold(target: Path, answers: dict) -> None:
    """Create project directory + baseline files.

    Delegates to `vessal init` for the bulk of the scaffold (which already
    writes a canonical .env.example with all three fields), then writes .env
    based on wizard answers. Does not touch .env.example.
    """
    import subprocess
    import sys

    if target.exists():
        raise CliUserError(f"{target} already exists")

    subprocess.check_call(
        [sys.executable, "-m", "vessal.cli", "init", answers["name"], "--no-venv"],
        cwd=str(target.parent),
    )

    env_path = target / ".env"
    env_path.write_text(
        _build_env_content(
            api_key=answers.get("api_key", ""),
            base_url=answers.get("base_url", ""),
            model=answers.get("model", ""),
        ),
        encoding="utf-8",
    )

    gitignore_path = target / ".gitignore"
    existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    if ".env" not in existing:
        gitignore_path.write_text(existing + "\n.env\n", encoding="utf-8")
