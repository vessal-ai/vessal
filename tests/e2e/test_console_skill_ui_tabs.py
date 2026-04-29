# tests/e2e/test_console_skill_ui_tabs.py
"""R13 e2e: Console renders a tab for every Skill that ships ui/index.html."""
from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

pytest.importorskip("playwright.async_api")
from playwright.async_api import async_playwright


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_console_lists_chat_ui_tab(tmp_path: Path):
    project = tmp_path / "my_agent"
    from vessal.ark.shell.cli.project_scaffold import write_project_scaffold
    write_project_scaffold(project, install_venv=True)

    port = _free_port()
    env = os.environ.copy()
    env["VESSAL_HTTP_PORT"] = str(port)
    proc = subprocess.Popen(
        [sys.executable, "-m", "vessal", "start", "--no-tui"],
        cwd=str(project),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        # Wait for HTTP server to be ready.
        for _ in range(120):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.5)
        else:
            raise RuntimeError("vessal start failed to come up")

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(f"http://127.0.0.1:{port}/")
            await page.wait_for_selector("[data-skill-tab='chat']", timeout=10_000)
            await browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
