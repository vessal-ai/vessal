"""test_inline_prompt — unit tests for inline keyboard-driven prompt helpers.

Tests bypass prompt_toolkit's interactive loop by injecting fake input
into the underlying prompt() call via monkeypatching.
"""
from __future__ import annotations

import pytest

from vessal.ark.shell.tui import inline_prompt


@pytest.fixture
def fake_prompt(monkeypatch):
    """Patch inline_prompt._prompt() to return a scripted sequence of inputs."""
    calls = []

    def factory(responses):
        iterator = iter(responses)

        def fake(*args, **kwargs):
            text = next(iterator)
            calls.append((args, kwargs, text))
            return text

        monkeypatch.setattr(inline_prompt, "_prompt", fake)
        return calls

    return factory


def test_ask_text_returns_input(fake_prompt):
    fake_prompt(["my-agent"])
    result = inline_prompt.ask_text("Project name", default="default-name")
    assert result == "my-agent"


def test_ask_text_empty_returns_default(fake_prompt):
    fake_prompt([""])
    result = inline_prompt.ask_text("Project name", default="default-name")
    assert result == "default-name"


def test_ask_choice_first_letter_matches(fake_prompt):
    fake_prompt(["y"])
    result = inline_prompt.ask_choice(
        "Pick provider",
        choices=[("yes", "Yes"), ("no", "No")],
        default="no",
    )
    assert result == "yes"


def test_ask_choice_empty_returns_default(fake_prompt):
    fake_prompt([""])
    result = inline_prompt.ask_choice(
        "Pick provider",
        choices=[("openai", "OpenAI"), ("other", "Other")],
        default="openai",
    )
    assert result == "openai"


def test_ask_yes_no_y(fake_prompt):
    fake_prompt(["y"])
    assert inline_prompt.ask_yes_no("Dockerize?", default=False) is True


def test_ask_yes_no_n(fake_prompt):
    fake_prompt(["n"])
    assert inline_prompt.ask_yes_no("Dockerize?", default=True) is False


def test_ask_yes_no_empty_returns_default(fake_prompt):
    fake_prompt([""])
    assert inline_prompt.ask_yes_no("Dockerize?", default=True) is True


def test_ask_text_validator_accepts_first_try(fake_prompt):
    fake_prompt(["good-name"])
    result = inline_prompt.ask_text(
        "Project name",
        default="my-agent",
        validator=lambda v: None,
    )
    assert result == "good-name"


def test_ask_text_validator_rejects_then_accepts(fake_prompt, capsys):
    fake_prompt(["bad", "good"])
    seen: list[str] = []

    def validator(value: str) -> str | None:
        seen.append(value)
        return "already exists" if value == "bad" else None

    result = inline_prompt.ask_text(
        "Project name",
        default="my-agent",
        validator=validator,
    )
    assert result == "good"
    assert seen == ["bad", "good"]
    captured = capsys.readouterr()
    assert "already exists" in captured.out


def test_ask_text_validator_runs_against_default(fake_prompt):
    """Validator must also check the default value when user presses Enter."""
    fake_prompt(["", "my-agent"])

    def validator(value: str) -> str | None:
        return "default reserved" if value == "default-name" else None

    result = inline_prompt.ask_text(
        "Project name",
        default="default-name",
        validator=validator,
    )
    assert result == "my-agent"
