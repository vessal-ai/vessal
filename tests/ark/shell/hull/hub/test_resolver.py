# src/vessal/ark/shell/hub/tests/test_resolver.py
"""Tests for source resolver."""
from pathlib import Path

import pytest

from vessal.ark.shell.hull.hub.resolver import ResolvedSource, resolve


SAMPLE_TOML = """\
[browser]
source = "vessal-ai/vessal-skills#skills/browser"
description = "web browsing"
tags = ["web"]
"""


@pytest.fixture
def registry_file(tmp_path: Path) -> Path:
    p = tmp_path / "registry.toml"
    p.write_text(SAMPLE_TOML, encoding="utf-8")
    return p


def test_resolve_short_name(registry_file: Path):
    result = resolve("browser", registry_path=registry_file)
    assert result.git_url == "https://github.com/vessal-ai/vessal-skills.git"
    assert result.subpath == "skills/browser"
    assert result.verified is True
    assert result.original == "browser"


def test_resolve_https_url():
    result = resolve("https://github.com/someone/my-skill.git")
    assert result.git_url == "https://github.com/someone/my-skill.git"
    assert result.subpath is None
    assert result.verified is False


def test_resolve_https_url_with_fragment():
    result = resolve("https://github.com/someone/skills-mono.git#skills/foo")
    assert result.git_url == "https://github.com/someone/skills-mono.git"
    assert result.subpath == "skills/foo"
    assert result.verified is False


def test_resolve_unknown_short_name(registry_file: Path):
    with pytest.raises(RuntimeError, match="not found in SkillHub"):
        resolve("nonexistent", registry_path=registry_file)
