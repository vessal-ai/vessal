"""test_supervisor.py — Integration tests for ShellServer subprocess management."""
import time
import pytest


def test_shell_server_spawns_hull_subprocess(tmp_path):
    """Hull subprocess is running after ShellServer starts."""
    from vessal.ark.shell.server import ShellServer

    # Create minimal hull.toml
    (tmp_path / "hull.toml").write_text(
        '[agent]\nname = "test"\n[hull]\nskills = []\nskill_paths = []\n'
        '[cell]\n[core]\n[core.api_params]\n'
    )
    (tmp_path / "SOUL.md").write_text("test agent")
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=test\nOPENAI_BASE_URL=http://localhost:1\n"
        "OPENAI_MODEL=test\n"
    )

    server = ShellServer(project_dir=str(tmp_path), port=0)
    try:
        server.start()
        assert server._hull_proc is not None
        assert server._hull_proc.poll() is None  # process is alive
        assert server._hull_alive is True
    finally:
        server.shutdown()


def test_shell_server_detects_hull_crash(tmp_path):
    """ShellServer detects a Hull subprocess crash and updates its state."""
    from vessal.ark.shell.server import ShellServer

    (tmp_path / "hull.toml").write_text(
        '[agent]\nname = "test"\n[hull]\nskills = []\nskill_paths = []\n'
        '[cell]\n[core]\n[core.api_params]\n'
    )
    (tmp_path / "SOUL.md").write_text("test agent")
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=test\nOPENAI_BASE_URL=http://localhost:1\n"
        "OPENAI_MODEL=test\n"
    )

    server = ShellServer(project_dir=str(tmp_path), port=0)
    try:
        server.start()
        # Disable auto-restart (test only verifies detection)
        server._stop_requested = True
        # Kill Hull subprocess
        server._hull_proc.kill()
        server._hull_proc.wait()
        # Poll until monitor detects the crash (up to 5 seconds)
        deadline = time.time() + 5
        while server._hull_alive and time.time() < deadline:
            time.sleep(0.2)
        assert not server._hull_alive
    finally:
        server.shutdown()
