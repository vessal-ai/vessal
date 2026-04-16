# src/vessal/ark/shell/hub/tests/test_registry.py
"""Tests for SkillHub registry fetch, search, and list."""
from pathlib import Path

import pytest

from vessal.ark.shell.hub.registry import Registry

SAMPLE_TOML = """\
[browser]
source = "vessal-ai/vessal-skills#skills/browser"
description = "web page browsing and scraping"
tags = ["web", "scraping"]

[telegram]
source = "someone/vessal-skill-telegram"
description = "telegram messaging"
tags = ["messaging", "social"]

[database]
source = "vessal-ai/vessal-skills#skills/database"
description = "database query execution"
tags = ["database", "sql"]
"""


@pytest.fixture
def registry(tmp_path: Path) -> Registry:
    """Registry loaded from a local file (bypasses network)."""
    toml_path = tmp_path / "registry.toml"
    toml_path.write_text(SAMPLE_TOML, encoding="utf-8")
    return Registry.from_file(toml_path)


def test_list_all(registry: Registry):
    entries = registry.list_all()
    assert len(entries) == 3
    names = [e["name"] for e in entries]
    assert "browser" in names
    assert "telegram" in names
    assert "database" in names


def test_list_paged(registry: Registry):
    page1 = registry.list_paged(page=1, per_page=2)
    assert len(page1) == 2
    page2 = registry.list_paged(page=2, per_page=2)
    assert len(page2) == 1
    page3 = registry.list_paged(page=3, per_page=2)
    assert len(page3) == 0


def test_search_by_name(registry: Registry):
    results = registry.search("browser")
    assert len(results) == 1
    assert results[0]["name"] == "browser"


def test_search_by_description(registry: Registry):
    results = registry.search("messaging")
    assert len(results) == 1
    assert results[0]["name"] == "telegram"


def test_search_by_tag(registry: Registry):
    results = registry.search("web")
    assert len(results) == 1
    assert results[0]["name"] == "browser"


def test_search_no_match(registry: Registry):
    results = registry.search("nonexistent")
    assert results == []


def test_resolve_known_name(registry: Registry):
    source = registry.resolve("browser")
    assert source == "vessal-ai/vessal-skills#skills/browser"


def test_resolve_unknown_name(registry: Registry):
    assert registry.resolve("unknown") is None
