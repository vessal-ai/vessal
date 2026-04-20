"""test_start_no_traceback_on_disconnect — R14 boot-surface regression.

Regression: ``vessal start`` must not print a Python traceback to stderr
when a keep-alive client abruptly closes its TCP socket.
Issue: console/3-executing/20260420-cli-traceback-noise.md (D1 reproducer #2)
"""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest


def _wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"server on port {port} never became reachable")


@pytest.fixture
def agent_project(tmp_path: Path):
    """Scaffold a minimal project via ``vessal init --no-venv`` and return its path.

    Writes a stub .env so openai.OpenAI() initialises without a real key.
    The test never makes an LLM call; it only verifies the HTTP layer.
    """
    subprocess.run(
        [sys.executable, "-m", "vessal.cli", "init", "agent", "--no-venv"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    project = tmp_path / "agent"
    (project / ".env").write_text(
        "OPENAI_API_KEY=sk-smoke-test-stub\n"
        "OPENAI_BASE_URL=http://127.0.0.1:1\n"
        "OPENAI_MODEL=gpt-4o\n",
        encoding="utf-8",
    )
    return project


def test_vessal_start_silent_on_client_disconnect(agent_project: Path):
    # Pick a non-default port to avoid clashing with any running instance.
    port = 18420
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "vessal.cli",
            "start",
            "--foreground",
            "--port",
            str(port),
        ],
        cwd=str(agent_project),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    try:
        _wait_for_port(port)

        # Half-open: connect, then RST without sending any bytes.
        for _ in range(5):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b"\x01\x00\x00\x00\x00\x00\x00\x00")
            s.connect(("127.0.0.1", port))
            s.close()
            time.sleep(0.05)

        # Give the server a moment to handle the disconnects.
        time.sleep(0.5)
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()

    assert "Traceback" not in stderr, f"Unexpected traceback on stderr:\n{stderr}"
    # Intentionally NOT asserting ``"ConnectionResetError" not in stderr``:
    # at DEBUG log level our own quiet-disconnect log line contains that
    # substring. The ``Traceback`` check above is the real contract — a bare
    # exception name in a structured log message is fine.
