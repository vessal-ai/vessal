"""components.py — UI component factory methods.

Each function returns a JSON-serializable dict:
  {"type": "<name>", "props": {...}, "children": [...]}
"""
from __future__ import annotations


def _component(type_name: str, children: list | None = None, **props) -> dict:
    """Internal: construct a component dict."""
    result = {"type": type_name, "props": props}
    if children is not None:
        result["children"] = list(children)  # shallow copy to avoid aliasing
    return result


def text(content: str, **props) -> dict:
    """Text component."""
    return _component("text", content=content, **props)


def card(children: list, **props) -> dict:
    """Card container."""
    return _component("card", children=children, **props)


def button(label: str, id: str | None = None, **props) -> dict:
    """Button. id is required for event identification."""
    if id is None:
        raise ValueError("button requires an id parameter for click event identification")
    return _component("button", label=label, id=id, **props)


def input_field(placeholder: str, id: str | None = None, **props) -> dict:
    """Input field."""
    if id is None:
        raise ValueError("input_field requires an id parameter")
    return _component("input", placeholder=placeholder, id=id, **props)


def panel(title: str, children: list, **props) -> dict:
    """Panel — a titled content block."""
    return _component("panel", children=children, title=title, **props)


def chart(data: list, kind: str = "bar", **props) -> dict:
    """Chart."""
    return _component("chart", data=data, kind=kind, **props)
