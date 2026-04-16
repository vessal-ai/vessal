# src/vessal/ark/shell/hub/tests/test_metadata.py
"""Tests for .installed.toml metadata read/write."""
from pathlib import Path
from vessal.ark.shell.hub.metadata import write_installed, read_installed, is_hub_installed


def test_write_and_read(tmp_path: Path):
    write_installed(
        skill_dir=tmp_path,
        source="vessal-ai/vessal-skills#skills/browser",
        version="1.0.0",
        verified=True,
    )
    toml_path = tmp_path / ".installed.toml"
    assert toml_path.exists()

    meta = read_installed(tmp_path)
    assert meta["source"] == "vessal-ai/vessal-skills#skills/browser"
    assert meta["version"] == "1.0.0"
    assert meta["verified"] is True
    assert "installed_at" in meta


def test_write_unverified(tmp_path: Path):
    write_installed(
        skill_dir=tmp_path,
        source="https://github.com/someone/skill-foo.git",
        version="0.2.0",
        verified=False,
    )
    meta = read_installed(tmp_path)
    assert meta["verified"] is False
    assert meta["source"] == "https://github.com/someone/skill-foo.git"


def test_read_missing(tmp_path: Path):
    meta = read_installed(tmp_path)
    assert meta is None


def test_is_hub_installed(tmp_path: Path):
    assert is_hub_installed(tmp_path) is False
    write_installed(tmp_path, source="x", version="0.1.0", verified=True)
    assert is_hub_installed(tmp_path) is True
