"""test_sync.py — Image → volume sync logic tests."""
from pathlib import Path

import pytest

from vessal.ark.shell.container.entry import sync_image_to_volume


@pytest.fixture
def image_dir(tmp_path):
    """Simulate /opt/agent-image/: agent definition in the image."""
    d = tmp_path / "image"
    d.mkdir()
    (d / "SOUL.md").write_text("I am agent")
    (d / "hull.toml").write_text('[agent]\nname = "test"\n')
    skills = d / "skills" / "chat"
    skills.mkdir(parents=True)
    (skills / "skill.py").write_text("class Chat: pass")
    (skills / "SKILL.md").write_text("# Chat")
    return d


@pytest.fixture
def volume_dir(tmp_path):
    """Simulate /app/agent/: empty named volume."""
    d = tmp_path / "volume"
    d.mkdir()
    return d


class TestFirstBoot:
    """Full copy when volume is empty."""

    def test_copies_all_files(self, image_dir, volume_dir):
        sync_image_to_volume(image_dir, volume_dir)
        assert (volume_dir / "SOUL.md").read_text() == "I am agent"
        assert (volume_dir / "hull.toml").exists()
        assert (volume_dir / "skills" / "chat" / "skill.py").exists()

    def test_creates_missing_dirs(self, image_dir, volume_dir):
        """data/, logs/, snapshots/ directories should be created."""
        sync_image_to_volume(image_dir, volume_dir)
        assert (volume_dir / "data").is_dir()
        assert (volume_dir / "logs").is_dir()
        assert (volume_dir / "snapshots").is_dir()

    def test_volume_dir_does_not_exist(self, image_dir, tmp_path):
        """First-boot path works even when volume_dst does not exist."""
        nonexistent = tmp_path / "nonexistent_volume"
        sync_image_to_volume(image_dir, nonexistent)
        assert (nonexistent / "SOUL.md").exists()
        assert (nonexistent / "data").is_dir()


class TestImageUpdate:
    """Selective overwrite when volume is non-empty."""

    def test_overwrites_soul_md(self, image_dir, volume_dir):
        """SOUL.md is overwritten with the image version."""
        (volume_dir / "hull.toml").write_text('[agent]\nname = "old"\n')
        (volume_dir / "SOUL.md").write_text("old soul")
        sync_image_to_volume(image_dir, volume_dir)
        assert (volume_dir / "SOUL.md").read_text() == "I am agent"

    def test_overwrites_hull_toml(self, image_dir, volume_dir):
        (volume_dir / "hull.toml").write_text('[agent]\nname = "old"\n')
        sync_image_to_volume(image_dir, volume_dir)
        assert "test" in (volume_dir / "hull.toml").read_text()

    def test_overwrites_skill_code(self, image_dir, volume_dir):
        """Skill code files are overwritten."""
        (volume_dir / "hull.toml").write_text("x")  # mark as initialized
        skill_dir = volume_dir / "skills" / "chat"
        skill_dir.mkdir(parents=True)
        (skill_dir / "skill.py").write_text("old code")
        sync_image_to_volume(image_dir, volume_dir)
        assert (skill_dir / "skill.py").read_text() == "class Chat: pass"

    def test_preserves_runtime_data(self, image_dir, volume_dir):
        """data/, logs/, snapshots/ are not overwritten."""
        (volume_dir / "hull.toml").write_text("x")  # mark as initialized
        (volume_dir / "data").mkdir()
        (volume_dir / "data" / "chat.jsonl").write_text('{"msg":"hi"}')
        (volume_dir / "logs").mkdir()
        (volume_dir / "logs" / "frames.jsonl").write_text('{"frame":1}')
        (volume_dir / "snapshots").mkdir()
        (volume_dir / "snapshots" / "snap.pkl").write_bytes(b"pickle")

        sync_image_to_volume(image_dir, volume_dir)

        assert (volume_dir / "data" / "chat.jsonl").read_text() == '{"msg":"hi"}'
        assert (volume_dir / "logs" / "frames.jsonl").read_text() == '{"frame":1}'
        assert (volume_dir / "snapshots" / "snap.pkl").read_bytes() == b"pickle"

    def test_preserves_skill_data_dir(self, image_dir, volume_dir):
        """skills/xxx/data/ is skill runtime data and is not overwritten."""
        (volume_dir / "hull.toml").write_text("x")  # mark as initialized
        skill_data = volume_dir / "skills" / "chat" / "data"
        skill_data.mkdir(parents=True)
        (skill_data / "chat.jsonl").write_text("precious data")

        sync_image_to_volume(image_dir, volume_dir)
        assert (skill_data / "chat.jsonl").read_text() == "precious data"

    def test_preserves_agent_created_skills(self, image_dir, volume_dir):
        """Agent-created skills (not present in the image) are not deleted."""
        (volume_dir / "hull.toml").write_text("x")  # mark as initialized
        custom = volume_dir / "skills" / "my_custom_skill"
        custom.mkdir(parents=True)
        (custom / "skill.py").write_text("custom skill")
        (custom / "SKILL.md").write_text("custom guide")

        sync_image_to_volume(image_dir, volume_dir)
        assert (custom / "skill.py").read_text() == "custom skill"
        assert (custom / "SKILL.md").read_text() == "custom guide"

    def test_syncs_non_sentinel_top_level_files(self, image_dir, volume_dir):
        """On image update, non-sentinel top-level files (e.g. requirements.txt) are also synced."""
        (volume_dir / "hull.toml").write_text("x")  # mark as initialized
        # Add a non-sentinel top-level file to the image
        (image_dir / "requirements.txt").write_text("openai>=1.0\n")

        sync_image_to_volume(image_dir, volume_dir)
        assert (volume_dir / "requirements.txt").read_text() == "openai>=1.0\n"
