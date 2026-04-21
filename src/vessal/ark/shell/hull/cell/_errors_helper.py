"""_errors_helper.py — Bounded ring buffer for _errors namespace variable.

Cap unit is ENTRIES. Default 200 (configurable via hull.toml [cell].error_buffer_cap).
"""
from __future__ import annotations
from typing import Any


def append_error(ns: dict, record: Any, cap: int | None = None) -> None:
    errors = ns.get("_errors", [])
    errors.append(record)
    effective_cap = cap if cap is not None else ns.get("_error_buffer_cap", 200)
    if len(errors) > effective_cap:
        errors = errors[-effective_cap:]
    ns["_errors"] = errors
