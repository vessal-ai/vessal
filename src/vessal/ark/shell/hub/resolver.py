# src/vessal/ark/shell/hub/resolver.py
"""Resolve install source strings to git URLs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from vessal.ark.shell.hub.registry import Registry


@dataclass
class ResolvedSource:
    """Result of resolving an install source string."""

    git_url: str
    subpath: str | None
    verified: bool
    original: str


def _parse_github_source(source: str) -> tuple[str, str | None]:
    """Parse 'owner/repo#subpath' into (git_url, subpath)."""
    if "#" in source:
        repo_part, subpath = source.split("#", 1)
    else:
        repo_part = source
        subpath = None
    git_url = f"https://github.com/{repo_part}.git"
    return git_url, subpath


def resolve(
    source: str,
    *,
    registry_path: Path | None = None,
) -> ResolvedSource:
    """Resolve a source string to a ResolvedSource.

    Source formats:
    - Short name: "browser" → looked up in registry
    - URL: "https://github.com/user/repo.git" → used directly
    - URL with fragment: "https://...#skills/foo" → URL + subpath

    Args:
        source: The install source string.
        registry_path: Optional local registry.toml path (for testing). If None, fetches remote.

    Returns:
        ResolvedSource with git_url, subpath, verified flag, and original source string.

    Raises:
        RuntimeError: If short name not found in registry.
    """
    parsed = urlparse(source)

    # URL source (starts with https:// or http://)
    if parsed.scheme in ("https", "http"):
        # Extract fragment as subpath
        git_url = source.split("#")[0]
        subpath = parsed.fragment or None
        return ResolvedSource(
            git_url=git_url,
            subpath=subpath,
            verified=False,
            original=source,
        )

    # Short name → look up in registry
    if registry_path is not None:
        registry = Registry.from_file(registry_path)
    else:
        registry = Registry.fetch()

    resolved = registry.resolve(source)
    if resolved is None:
        raise RuntimeError(
            f"Skill '{source}' not found in SkillHub registry. "
            f"Use a full URL to install from an external source."
        )

    git_url, subpath = _parse_github_source(resolved)
    return ResolvedSource(
        git_url=git_url,
        subpath=subpath,
        verified=True,
        original=source,
    )
