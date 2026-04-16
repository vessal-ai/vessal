# src/vessal/ark/shell/hub/registry.py
"""SkillHub registry: fetch, search, and resolve skill names."""
from __future__ import annotations

import logging
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)

REGISTRY_URL = (
    "https://raw.githubusercontent.com/vessal-ai/vessal-skills/main/registry.toml"
)


class Registry:
    """In-memory representation of a SkillHub registry.toml."""

    def __init__(self, entries: dict[str, dict]):
        self._entries = entries

    @classmethod
    def from_file(cls, path: Path) -> Registry:
        """Load registry from a local TOML file."""
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(data)

    @classmethod
    def fetch(cls) -> Registry:
        """Fetch registry.toml from the SkillHub remote repository."""
        import urllib.request

        try:
            with urllib.request.urlopen(REGISTRY_URL, timeout=15) as resp:
                data = tomllib.loads(resp.read().decode("utf-8"))
            return cls(data)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch SkillHub registry: {e}") from e

    def list_all(self) -> list[dict]:
        """List all entries as dicts with name, source, description, tags."""
        return [
            {
                "name": name,
                "source": info.get("source", ""),
                "description": info.get("description", ""),
                "tags": info.get("tags", []),
            }
            for name, info in self._entries.items()
        ]

    def list_paged(self, page: int = 1, per_page: int = 20) -> list[dict]:
        """List entries with pagination."""
        all_entries = self.list_all()
        start = (page - 1) * per_page
        return all_entries[start : start + per_page]

    def search(self, keyword: str) -> list[dict]:
        """Search entries by keyword (matches name, description, tags)."""
        keyword_lower = keyword.lower()
        results = []
        for name, info in self._entries.items():
            haystack = (
                name.lower()
                + " " + info.get("description", "").lower()
                + " " + " ".join(info.get("tags", []))
            )
            if keyword_lower in haystack:
                results.append({
                    "name": name,
                    "source": info.get("source", ""),
                    "description": info.get("description", ""),
                    "tags": info.get("tags", []),
                })
        return results

    def resolve(self, name: str) -> str | None:
        """Resolve a short name to its source string. Returns None if not found."""
        entry = self._entries.get(name)
        if entry is None:
            return None
        return entry.get("source")
