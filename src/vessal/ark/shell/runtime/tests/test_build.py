"""test_build.py — vessal build context assembly tests."""
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from vessal.ark.shell.runtime.container.build import assemble_build_context, build_image


@pytest.fixture
def agent_dir(tmp_path):
    """Minimal agent directory."""
    (tmp_path / "hull.toml").write_text('[agent]\nname = "test-agent"\n')
    (tmp_path / "SOUL.md").write_text("I am a test agent.")
    (tmp_path / "skills").mkdir()
    return tmp_path


class TestAssembleBuildContext:
    """assemble_build_context copies vessal + agent into temp dir."""

    def test_copies_agent_dir(self, agent_dir, tmp_path):
        ctx = tmp_path / "ctx"
        assemble_build_context(agent_dir, ctx)
        assert (ctx / "agent" / "hull.toml").exists()
        assert (ctx / "agent" / "SOUL.md").exists()

    def test_copies_vessal_source(self, agent_dir, tmp_path):
        ctx = tmp_path / "ctx"
        assemble_build_context(agent_dir, ctx)
        # vessal source should be at ctx/vessal/ and contain pyproject.toml
        assert (ctx / "vessal").is_dir()
        assert (ctx / "vessal" / "pyproject.toml").exists()

    def test_copies_dockerfile(self, agent_dir, tmp_path):
        ctx = tmp_path / "ctx"
        assemble_build_context(agent_dir, ctx)
        assert (ctx / "Dockerfile").exists()
        assert "ENTRYPOINT" in (ctx / "Dockerfile").read_text()

    def test_agent_override_dockerfile(self, agent_dir, tmp_path):
        """Agent can provide its own Dockerfile."""
        (agent_dir / "Dockerfile").write_text("FROM custom:latest\n")
        ctx = tmp_path / "ctx"
        assemble_build_context(agent_dir, ctx)
        assert "custom:latest" in (ctx / "Dockerfile").read_text()

    def test_rejects_missing_hull_toml(self, tmp_path):
        agent_dir = tmp_path / "bad"
        agent_dir.mkdir()
        with pytest.raises(FileNotFoundError, match="hull.toml"):
            assemble_build_context(agent_dir, tmp_path / "ctx")

    def test_excludes_dot_env(self, agent_dir, tmp_path):
        """Secrets (.env) must NOT be copied into the build context."""
        (agent_dir / ".env").write_text("OPENAI_API_KEY=secret\n")
        ctx = tmp_path / "ctx"
        assemble_build_context(agent_dir, ctx)
        assert not (ctx / "agent" / ".env").exists()

    def test_excludes_data_dir(self, agent_dir, tmp_path):
        """data/ (snapshots, frames) must NOT be copied."""
        (agent_dir / "data").mkdir()
        (agent_dir / "data" / "snapshot.pkl").write_bytes(b"x")
        ctx = tmp_path / "ctx"
        assemble_build_context(agent_dir, ctx)
        assert not (ctx / "agent" / "data").exists()


class TestBuildImage:
    """build_image runs docker build with correct args."""

    @patch("subprocess.run")
    def test_calls_docker_build(self, mock_run, agent_dir, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        build_image(agent_dir, name="test-agent")
        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "docker"
        assert cmd[1] == "build"
        assert "-t" in cmd
        assert "test-agent:latest" in cmd

    @patch("subprocess.run")
    def test_reads_name_from_hull_toml_when_not_given(self, mock_run, agent_dir):
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        build_image(agent_dir)  # no name argument
        cmd = mock_run.call_args[0][0]
        assert "test-agent:latest" in cmd


class TestReadAgentName:
    """_read_agent_name parses hull.toml correctly."""

    def test_reads_name(self, agent_dir):
        from vessal.ark.shell.runtime.container.build import _read_agent_name
        assert _read_agent_name(agent_dir) == "test-agent"

    def test_raises_if_no_hull_toml(self, tmp_path):
        from vessal.ark.shell.runtime.container.build import _read_agent_name
        with pytest.raises(FileNotFoundError):
            _read_agent_name(tmp_path)


class TestRunContainer:
    """run_container uses correct volume name and mount point."""

    @patch("subprocess.run")
    def test_volume_mounts_whole_agent_dir(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        from vessal.ark.shell.runtime.container.build import run_container
        run_container("test-agent", port=9999)
        # Find docker run call (second call — first is docker volume create)
        run_calls = [c for c in mock_run.call_args_list if c[0][0][1] == "run"]
        assert len(run_calls) == 1
        cmd = run_calls[0][0][0]
        # Volume mount should be /app/agent not /app/agent/data
        v_idx = cmd.index("-v")
        mount = cmd[v_idx + 1]
        assert mount.endswith(":/app/agent"), f"Expected :/app/agent, got {mount}"
        assert "test-agent_agent" in mount

    @patch("subprocess.run")
    def test_volume_name_uses_agent_suffix(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        from vessal.ark.shell.runtime.container.build import run_container
        run_container("my-bot", port=8420)
        # docker volume create is the first subprocess.run call
        create_call = mock_run.call_args_list[0]
        cmd = create_call[0][0]
        assert cmd == ["docker", "volume", "create", "my-bot_agent"]
