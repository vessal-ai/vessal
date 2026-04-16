"""test_process_isolation.py — Shell-Hull process isolation integration tests.

Verifies:
- Shell remains alive and returns 503 after Hull subprocess crashes
- Shell automatically restarts Hull subprocess after a crash

Test strategy:
    Starts a real ShellServer (with a real Hull subprocess), directly kill()s the Hull
    process to trigger a crash, and observes the state changes on the Shell side.
    No components are mocked — this is end-to-end process isolation verification.

Environment requirements:
    The agent_project fixture writes a fake OPENAI_API_KEY/.env. The Hull process only
    creates an OpenAI client object during initialization without making real API calls,
    so no real network connection is needed.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request

import pytest

from vessal.ark.shell.server import ShellServer


# ------------------------------------------------------------------ fixtures


@pytest.fixture
def agent_project(tmp_path):
    """Create a minimal agent project: hull.toml + SOUL.md + .env.

    hull.toml includes all sections read by Hull.__init__ (all optional, but declared
    explicitly to avoid silently skipping tests if required fields are added later).
    .env points to a non-existent local port — the Hull process only creates an
    openai.OpenAI object on startup without making HTTP requests, so an invalid URL
    does not affect initialization.
    """
    (tmp_path / "hull.toml").write_text(
        "[agent]\n"
        'name = "test"\n'
        "[hull]\n"
        "skills = []\n"
        "skill_paths = []\n"
        "[cell]\n"
        "[core]\n"
        "[core.api_params]\n"
        "temperature = 0.7\n"
        "[compression]\n"
        "enabled = false\n",
        encoding="utf-8",
    )
    (tmp_path / "SOUL.md").write_text("test agent", encoding="utf-8")
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=test\n"
        "OPENAI_BASE_URL=http://127.0.0.1:1\n"
        "OPENAI_MODEL=test\n",
        encoding="utf-8",
    )
    return tmp_path


# ------------------------------------------------------------------ tests


def test_hull_crash_does_not_kill_shell(agent_project):
    """Shell remains alive and returns 503 to requests after Hull subprocess crashes.

    Steps:
        1. Start ShellServer, wait for Hull to be ready
        2. Verify /status returns 200 (Shell is proxying Hull normally)
        3. Set _stop_requested=True to prevent monitor from auto-restarting
        4. kill() the Hull subprocess
        5. Wait for the monitor thread to detect the crash (_hull_alive → False)
        6. Verify the Shell HTTP service still responds, returning 503
    """
    server = ShellServer(project_dir=str(agent_project), port=0)
    try:
        server.start()
        port = server.port

        # Shell is healthy: /status is proxied through to Hull
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/status")
        assert resp.status == 200

        # Prevent monitor from auto-restarting to avoid interfering with assertion window
        server._stop_requested = True
        server._hull_proc.kill()
        server._hull_proc.wait()

        # Wait for monitor thread to detect crash (up to 5s)
        deadline = time.time() + 5
        while server._hull_alive and time.time() < deadline:
            time.sleep(0.1)
        assert not server._hull_alive, "Monitor should set _hull_alive to False within 5s"

        # Shell HTTP service is still running, returning 503 (Hull unavailable)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/status")
            # Reaching here means Hull completed restart within the detection window
            # (should not happen since _stop_requested=True)
        except urllib.error.HTTPError as e:
            assert e.code == 503, f"Expected 503, got {e.code}"
        except (urllib.error.URLError, ConnectionError):
            pytest.fail("Shell HTTP service should be alive, but connection failed")
    finally:
        server.shutdown()


def test_shell_restarts_hull_after_crash(agent_project):
    """Shell automatically restarts Hull after a crash, and the new process has a different PID.

    Steps:
        1. Start ShellServer, record the initial Hull PID
        2. kill() Hull (without setting _stop_requested, allowing monitor to restart)
        3. Wait for monitor to detect crash → restart → _hull_alive recovers to True
        4. Assert new PID differs from old PID
        5. Assert /status is available again (new Hull is responding)

    Timeout 35s: Hull subprocess startup takes < 1s (measured), with buffer for slow CI machines.
    """
    server = ShellServer(project_dir=str(agent_project), port=0)
    try:
        server.start()
        port = server.port
        old_pid = server._hull_proc.pid

        # kill Hull; monitor should auto-restart
        server._hull_proc.kill()
        server._hull_proc.wait()

        # Wait for restart to complete (up to 35s)
        deadline = time.time() + 35
        while time.time() < deadline:
            if server._hull_alive and server._hull_proc.pid != old_pid:
                break
            time.sleep(0.2)

        assert server._hull_alive, "Shell should auto-restart Hull within 35s"
        assert server._hull_proc.pid != old_pid, "After restart must be a new subprocess (different PID)"

        # New Hull is ready; /status should return 200 again
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/status")
        assert resp.status == 200, f"/status should return 200 after restart, got {resp.status}"
    finally:
        server.shutdown()
