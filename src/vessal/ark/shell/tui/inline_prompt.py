"""inline_prompt — keyboard-driven inline prompt primitives.

Replaces prompt_toolkit.shortcuts.*_dialog (the blue fullscreen dialogs) with
single-line inline prompts. Enter accepts the default; no mouse required.

All three helpers accept a `default` parameter and return a native Python value.
"""
from __future__ import annotations

from typing import Sequence

from prompt_toolkit import prompt as _prompt


def ask_text(question: str, *, default: str = "") -> str:
    """Ask for a single line of free text.

    Renders: "<question> [default]: " and returns the user's input.
    Empty input returns the default.
    """
    suffix = f" [{default}]" if default else ""
    raw = _prompt(f"{question}{suffix}: ")
    return raw.strip() or default


def ask_choice(
    question: str,
    *,
    choices: Sequence[tuple[str, str]],
    default: str,
) -> str:
    """Ask for a single choice from a fixed list.

    choices is a list of (value, label) pairs. Match is by first letter of value
    (case-insensitive) or by full value. Empty input returns the default.
    """
    if not choices:
        raise ValueError("choices must not be empty")
    values = [v for v, _ in choices]
    if default not in values:
        raise ValueError(f"default {default!r} not in choice values {values}")

    labels = " / ".join(
        f"[{v[0].upper()}]{label[1:]}" if label.lower().startswith(v[0].lower()) else f"{v} ({label})"
        for v, label in choices
    )
    raw = _prompt(f"{question} ({labels}) [{default}]: ").strip().lower()
    if not raw:
        return default
    for v, _ in choices:
        if raw == v.lower() or raw[:1] == v[:1].lower():
            return v
    # Unknown input → fall back to default rather than loop; simple & predictable.
    return default


def ask_yes_no(question: str, *, default: bool) -> bool:
    """Ask a yes/no question.

    Accepts y/yes/n/no (case-insensitive). Empty input returns the default.
    """
    hint = "[Y/n]" if default else "[y/N]"
    raw = _prompt(f"{question} {hint}: ").strip().lower()
    if not raw:
        return default
    if raw in ("y", "yes"):
        return True
    if raw in ("n", "no"):
        return False
    return default
