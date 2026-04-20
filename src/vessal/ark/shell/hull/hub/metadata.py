# src/vessal/ark/shell/hub/metadata.py
"""Read/write .installed.toml metadata for hub-installed skills."""
from __future__ import annotations

import tomllib
from datetime import datetime, timezone
from pathlib import Path

_FILENAME = ".installed.toml"


def _toml_str(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def write_installed(
    skill_dir: Path,
    source: str,
    version: str,
    verified: bool,
) -> None:
    """Write .installed.toml into a skill directory."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    content = (
        f'source = "{_toml_str(source)}"\n'
        f'version = "{_toml_str(version)}"\n'
        f'installed_at = "{now}"\n'
        f'verified = {"true" if verified else "false"}\n'
    )
    (skill_dir / _FILENAME).write_text(content, encoding="utf-8")


def read_installed(skill_dir: Path) -> dict | None:
    """Read .installed.toml from a skill directory. Returns None if not found."""

    path = skill_dir / _FILENAME
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return tomllib.load(f)


def is_hub_installed(skill_dir: Path) -> bool:
    """Check whether a skill directory was installed from SkillHub."""
    return (skill_dir / _FILENAME).exists()
