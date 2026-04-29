"""R14 smoke test: vessal start must serve /frames and /wake without
cross-thread SQLite crashes in hull.log."""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
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


def _http_get(url: str, timeout: float = 5.0) -> tuple[int, dict]:
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()}


def _http_post_json(url: str, body: dict, timeout: float = 5.0) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()}


@pytest.fixture
def agent_project(tmp_path: Path):
    from vessal.ark.shell.cli.project_scaffold import write_project_scaffold

    project = tmp_path / "agent"
    write_project_scaffold(project, install_venv=False)
    (project / ".env").write_text(
        "OPENAI_API_KEY=sk-smoke-test-stub\n"
        "OPENAI_BASE_URL=http://127.0.0.1:1\n"
        "OPENAI_MODEL=gpt-4o\n",
        encoding="utf-8",
    )
    return project


def test_frames_endpoint_does_not_crash_hull(agent_project: Path):
    port = 18422
    proc = subprocess.Popen(
        [sys.executable, "-m", "vessal.cli", "start",
         "--foreground", "--port", str(port)],
        cwd=str(agent_project),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    try:
        _wait_for_port(port)
        time.sleep(1.0)

        status, body = _http_get(f"http://127.0.0.1:{port}/status")
        assert status == 200, f"/status returned {status}: {body}"

        status, body = _http_get(f"http://127.0.0.1:{port}/frames?after=0")
        assert status == 200, f"/frames returned {status}: {body}"
        assert "frames" in body
        assert isinstance(body["frames"], list)

        status, _ = _http_post_json(
            f"http://127.0.0.1:{port}/wake", {"reason": "smoke-test"}
        )
        assert status == 200

        time.sleep(2.0)

        status, _ = _http_get(f"http://127.0.0.1:{port}/frames?after=0")
        assert status == 200

    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()

    log_path = agent_project / "data" / "hull.log"
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        assert "sqlite3.ProgrammingError" not in log_text, (
            f"Found cross-thread SQLite error in hull.log:\n{log_text[-2000:]}"
        )
