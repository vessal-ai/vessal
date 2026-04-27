"""test_console_assets.py — Console SPA assets reference flat wire fields.

R13 mandates Playwright tests for user-facing surface, but Playwright is not yet
a dev dep. This file is a pragmatic stand-in: it asserts that app.js / index.html
reference the new flat wire field names (pong_operation etc.) and do NOT reference
the legacy nested ones (pong.action.operation etc.). When Playwright lands, this
file should be replaced by a real DOM rendering test.

Asserts the C14 invariant for PR 1c: wire shape = SQLite frame_content columns.
"""
from __future__ import annotations

from pathlib import Path

CONSOLE_ROOT = Path(__file__).resolve().parents[3] / "src/vessal/console_spa"


def _read(rel: str) -> str:
    return (CONSOLE_ROOT / rel).read_text(encoding="utf-8")


def test_app_js_uses_flat_field_names() -> None:
    src = _read("assets/app.js")
    assert "pong_operation" in src, "app.js must read f.pong_operation (flat field)"
    assert "pong_think" in src, "app.js must read f.pong_think (flat field)"
    assert "obs_stdout" in src, "app.js must read f.obs_stdout (flat field)"


def test_app_js_does_not_use_legacy_nested_paths() -> None:
    src = _read("assets/app.js")
    forbidden = [
        "pong.action.operation",
        "pong?.action?.operation",
        "pong.action.expect",
        "pong?.action?.expect",
        "pong?.think",
        "observation?.stdout",
        "observation?.error",
    ]
    offenders = [p for p in forbidden if p in src]
    assert offenders == [], f"app.js still references legacy nested paths: {offenders}"


def test_app_js_uses_n_not_number() -> None:
    src = _read("assets/app.js")
    assert "f.number" not in src, "app.js must use f.n (was f.number)"
    assert "x.number" not in src, "app.js must use x.n inside findIndex (was x.number)"
    assert ".n ===" in src or "f.n" in src or 'frame.n' in src, "app.js must read f.n somewhere"


def test_index_html_uses_flat_field_names() -> None:
    src = _read("index.html")
    assert "pong_operation" in src or "pong_think" in src, (
        "index.html must reference flat fields (pong_think / pong_operation)"
    )
    forbidden = ["pong?.action", "pong.action", "observation?.stdout", "observation?.error"]
    offenders = [p for p in forbidden if p in src]
    assert offenders == [], f"index.html still references legacy nested paths: {offenders}"
