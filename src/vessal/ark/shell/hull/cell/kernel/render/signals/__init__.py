"""signals/__init__.py — Kernel base signal module.

BASE_SIGNALS is a list of always-present signal functions that do not depend on any Skill.
Each entry is a (name, fn) tuple. Skill signals are collected by Kernel.update_signals()
via duck-typing scan.

Signal function protocol: fn(ns: dict) -> str
  Returns non-empty string = has content, included in rendering.
  Returns empty string     = no content, skipped in rendering.
"""

from vessal.ark.shell.hull.cell.kernel.render.signals import (
    dropped_keys,
    errors,
    namespace_dir,
    system_vars,
    verdict,
)

BASE_SIGNALS: list[tuple[str, callable]] = [
    ("verdict", verdict.render),
    ("namespace directory", namespace_dir.render),
    ("system", system_vars.render),
    ("reconstruction hint", dropped_keys.render),
    ("errors", errors.render),
]

__all__ = ["BASE_SIGNALS"]
