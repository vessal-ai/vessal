# src/vessal/ark/shell/hub/tests/test_integration.py
"""Integration test for the full skill install flow (local, no network)."""
from pathlib import Path

import pytest

from vessal.ark.shell.hull.hub.installer import locate_skill_in_repo, copy_skill
from vessal.ark.shell.hull.hub.metadata import write_installed, read_installed, is_hub_installed
from vessal.ark.shell.hull.hub.registry import Registry
from vessal.ark.shell.hull.hub.resolver import resolve


def _make_skill_repo(base: Path, name: str = "test_skill") -> Path:
    """Create a minimal skill in a directory (simulating a cloned repo)."""
    repo = base / "repo"
    repo.mkdir()
    class_name = "".join(part.capitalize() for part in name.split("_"))
    (repo / "__init__.py").write_text(f"from .skill import {class_name} as Skill\n")
    (repo / "skill.py").write_text(
        f"from vessal.ark.shell.hull.skill import SkillBase\n\n"
        f"class {class_name}(SkillBase):\n"
        f"    name = '{name}'\n"
        f"    description = 'test skill'\n"
    )
    (repo / "SKILL.md").write_text(
        f'---\nname: {name}\nversion: "1.0.0"\ndescription: "test skill"\n'
        f'author: "tester"\nlicense: "MIT"\nrequires:\n  skills: []\n---\n\nGuide.'
    )
    return repo


def test_full_local_flow(tmp_path: Path):
    """Test: resolve short name → locate → copy → metadata."""
    # Set up registry
    registry_path = tmp_path / "registry.toml"
    registry_path.write_text(
        '[test_skill]\nsource = "tester/test-skill"\n'
        'description = "a test skill"\ntags = ["test"]\n'
    )

    # Resolve
    resolved = resolve("test_skill", registry_path=registry_path)
    assert resolved.verified is True
    assert "tester/test-skill" in resolved.git_url

    # Set up a "cloned" repo (simulate what clone_repo would produce)
    repo = _make_skill_repo(tmp_path)

    # Locate
    skill_dir = locate_skill_in_repo(repo, subpath=None)
    assert (skill_dir / "SKILL.md").exists()

    # Copy
    hub_dir = tmp_path / "project" / "skills" / "hub"
    hub_dir.mkdir(parents=True)
    dest = copy_skill(skill_dir, hub_dir, "test_skill")
    assert dest.is_dir()
    assert (dest / "SKILL.md").exists()

    # Metadata
    write_installed(dest, source=resolved.original, version="1.0.0", verified=True)
    assert is_hub_installed(dest)
    meta = read_installed(dest)
    assert meta["source"] == "test_skill"
    assert meta["version"] == "1.0.0"
    assert meta["verified"] is True


def test_registry_search(tmp_path: Path):
    """Test: search registry by keyword."""
    registry_path = tmp_path / "registry.toml"
    registry_path.write_text(
        '[browser]\nsource = "x"\ndescription = "web browsing"\ntags = ["web"]\n\n'
        '[database]\nsource = "y"\ndescription = "sql queries"\ntags = ["sql"]\n'
    )
    registry = Registry.from_file(registry_path)

    assert len(registry.search("web")) == 1
    assert registry.search("web")[0]["name"] == "browser"
    assert len(registry.search("sql")) == 1
    assert len(registry.search("nonexistent")) == 0
    assert len(registry.list_all()) == 2


def test_v1_frontmatter_parsing(tmp_path: Path):
    """Test: SKILL.md v1 frontmatter parsed correctly."""
    from vessal.ark.shell.hull.skill_manager import _parse_skill_md

    md = tmp_path / "SKILL.md"
    md.write_text(
        '---\nname: browser\nversion: "2.0.0"\ndescription: "browse"\n'
        'author: "vessal-ai"\nlicense: "Apache-2.0"\nrequires:\n  skills: [tasks]\n  python: ">=3.12"\n'
        '---\n\n# browser\n\nGuide body.'
    )
    meta, body = _parse_skill_md(md)
    assert meta["name"] == "browser"
    assert meta["version"] == "2.0.0"
    assert meta["requires"]["skills"] == ["tasks"]
    assert meta["requires"]["python"] == ">=3.12"
    assert "Guide body." in body
