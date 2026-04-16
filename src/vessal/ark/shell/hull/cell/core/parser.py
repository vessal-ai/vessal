# src/vessal/ark/cell/core/parser.py
"""parser.py — LLM response parser (pure functions).

Parsing rules:
- <action> must appear at least once (maps to Pong.action.operation)
- <think> is optional
- <expect> is optional
- When any tag is duplicated, the last occurrence is used (reasoning models
  may produce example tags in their reasoning content)
- ParseError is raised when <action> content is pure whitespace
"""
from __future__ import annotations

import re

from vessal.ark.shell.hull.cell.protocol import Action, Pong

_TAG_PATTERN = re.compile(
    r"<(action|think|expect)>(.*?)</\1>",
    re.DOTALL,
)


class ParseError(ValueError):
    """Response parsing failed. Subclass of ValueError."""


def parse_response(text: str) -> Pong:
    """Parse LLM response text into a Pong structure.

    Extracts <think>, <action>, and <expect> tags from the text.
    When a tag is duplicated, the last occurrence is used (tolerates
    example tags produced by reasoning models during their reasoning process).

    Args:
        text: The complete raw output text from the LLM (message.content).

    Returns:
        Pong containing think (reasoning process) and action (Action(operation, expect)).

    Raises:
        ParseError: Response contains no <action> tag, or <action> content is pure whitespace.
    """
    actions: list[str] = []
    thinks: list[str] = []
    expects: list[str] = []

    for tag_name, content in _TAG_PATTERN.findall(text):
        if tag_name == "action":
            actions.append(content)
        elif tag_name == "think":
            thinks.append(content)
        elif tag_name == "expect":
            expects.append(content)

    if len(actions) == 0:
        raise ParseError("No <action> tag found in response")

    # When think/expect are duplicated, use the last one (reasoning models may
    # produce example tags during reasoning). Same for action, but at least one
    # must exist.
    operation = actions[-1].strip()
    if not operation:
        raise ParseError("<action> tag content is empty")

    return Pong(
        think=thinks[-1].strip() if thinks else "",
        action=Action(
            operation=operation,
            expect=expects[-1].strip() if expects else "",
        ),
    )
