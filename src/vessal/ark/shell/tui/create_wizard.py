"""create_wizard.py — 6-question wizard invoked by `vessal create` or the TUI picker."""
from __future__ import annotations

from pathlib import Path

DEFAULT_ANSWERS = {
    "name": "my-agent",
    "provider": "openai",
    "api_key": "",
    "template": "blank",
    "dockerize": False,
    "deploy": False,
}


def finalize_answers(user_answers: dict) -> dict:
    """Fill missing fields with defaults; validate."""
    merged = dict(DEFAULT_ANSWERS)
    merged.update({k: v for k, v in user_answers.items() if v is not None})
    if not merged["name"]:
        raise ValueError("name cannot be empty")
    return merged


def run(cwd: Path | None = None) -> int:
    from prompt_toolkit.shortcuts import input_dialog, yes_no_dialog, radiolist_dialog

    cwd = (cwd or Path.cwd()).resolve()
    answers: dict = {}
    name = input_dialog(title="1/6 · Project name", text="Enter project name", default=DEFAULT_ANSWERS["name"]).run()
    if name is None:
        return 0
    answers["name"] = name or DEFAULT_ANSWERS["name"]

    provider = radiolist_dialog(
        title="2/6 · Provider",
        text="Pick an LLM provider",
        values=[("openai", "OpenAI"), ("anthropic", "Anthropic"), ("other", "Other (edit hull.toml later)")],
        default=DEFAULT_ANSWERS["provider"],
    ).run()
    answers["provider"] = provider or DEFAULT_ANSWERS["provider"]

    key = input_dialog(title="3/6 · API key", text="Paste your API key (stored in .env, gitignored). Leave blank to edit later.").run()
    answers["api_key"] = key or ""

    template = radiolist_dialog(
        title="4/6 · Starter",
        text="Pick a template",
        values=[("blank", "Blank"), ("chat", "Chat bot"), ("tool", "Tool-calling agent")],
        default=DEFAULT_ANSWERS["template"],
    ).run()
    answers["template"] = template or DEFAULT_ANSWERS["template"]

    answers["dockerize"] = bool(yes_no_dialog(title="5/6 · Dockerize?", text="Generate a Dockerfile now?").run())
    answers["deploy"] = bool(yes_no_dialog(title="6/6 · Deploy preflight?", text="Set up deploy hooks?").run())

    finalized = finalize_answers(answers)
    _scaffold(cwd / finalized["name"], finalized)
    print(f"Project created at {cwd / finalized['name']}")
    return 0


def _scaffold(target: Path, answers: dict) -> None:
    """Create project directory + baseline files.

    Delegates to the existing `vessal init` logic for the bulk of the work, then
    writes .env / .env.example / .gitignore based on wizard answers.
    """
    import subprocess
    import sys

    if target.exists():
        raise FileExistsError(f"{target} already exists")

    subprocess.check_call(
        [sys.executable, "-m", "vessal.cli", "init", answers["name"], "--no-venv"],
        cwd=str(target.parent),
    )

    env_path = target / ".env"
    env_example_path = target / ".env.example"
    gitignore_path = target / ".gitignore"

    key_var = "OPENAI_API_KEY" if answers["provider"] == "openai" else "LLM_API_KEY"
    env_example_path.write_text(f"{key_var}=\n", encoding="utf-8")
    if answers["api_key"]:
        env_path.write_text(f"{key_var}={answers['api_key']}\n", encoding="utf-8")

    existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    if ".env" not in existing:
        gitignore_path.write_text(existing + "\n.env\n", encoding="utf-8")
