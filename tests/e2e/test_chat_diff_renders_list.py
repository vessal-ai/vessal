"""Playwright e2e: chat Skill renderDiff shows list[{op,name,type}] correctly (R13)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def render_html(tmp_path: Path):
    """Synthesize a minimal HTML harness that loads render.js and feeds it a frame."""
    repo_root = Path(__file__).parent.parent.parent
    render_js = (repo_root / "src/vessal/skills/chat/ui/render.js").read_text()
    frame_payload = {
        "number": 1,
        "ping": {},
        "pong": {"think": "", "action": {"operation": "x = 1", "expect": ""}},
        "observation": {
            "stdout": "",
            "stderr": "",
            "diff": [{"op": "+", "name": "x", "type": "int"}],
            "error": None,
            "verdict": None,
        },
    }
    html = (
        "<!doctype html><html><body>"
        "<div id='out'></div>"
        f"<script>{render_js}</script>"
        "<script>"
        f"const frame = {json.dumps(frame_payload)};"
        "document.getElementById('out').innerHTML = renderFrame(frame, new Set(['diff']));"
        "</script></body></html>"
    )
    p = tmp_path / "harness.html"
    p.write_text(html)
    return p


def test_diff_list_renders_to_dom(render_html: Path):
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file://{render_html}")
        out_text = page.locator("#out").inner_text()
        # The plus-row from the diff list should be rendered, including name and type.
        assert "+ x: int" in out_text or ("x" in out_text and "int" in out_text)
        browser.close()
