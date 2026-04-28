"""skill — Memory Skill implementation."""
import json
import os
from pathlib import Path

from vessal.skills._base import BaseSkill


class Memory(BaseSkill):
    """Cross-session key-value memory. Agent calls save/get/delete to manage memory entries.

    Attributes:
        _store: In-memory dict mapping key → value.
        _data_dir: Data directory path; None when no ns is provided.
        _ns: Reference to Hull namespace; None when no ns is provided. Required by drop().
    """

    name = "memory"
    description = "cross-session memory"

    def __init__(self) -> None:
        super().__init__()
        self._store: dict = {}
        self._ns: dict | None = None
        self._data_dir: Path | None = None

        base = os.environ.get("VESSAL_DATA_DIR")
        if base:
            self._data_dir = Path(base) / "memory"
            self._data_dir.mkdir(parents=True, exist_ok=True)
            self._load()

        print("memory: save(k,v)/get(k)/delete(k) — cross-session key-value store")

    def save(self, key: str, value: object) -> None:
        """Save a memory entry and write to disk immediately.

        Args:
            key: Memory key name.
            value: Any JSON-serializable value.
        """
        self._store[key] = value
        self._persist()

    def get(self, key: str) -> object:
        """Retrieve a memory entry.

        Args:
            key: Memory key name.

        Returns:
            The stored value, or None if not found.
        """
        return self._store.get(key)

    def delete(self, key: str) -> None:
        """Delete a memory entry.

        Args:
            key: Memory key name (silently ignored if not found).
        """
        self._store.pop(key, None)
        self._persist()

    def drop(self, n: int) -> None:
        """Not implemented: frame storage moved to SQLite in PR 5. Will be re-implemented in PR-Compaction-Cell."""
        print("⚠ memory.drop() is not available: frame storage has moved to SQLite. Use memory.save() to preserve key information.")

    def signal_update(self) -> None:
        """Per-frame: memory entries + context pressure warning."""
        lines: list[str] = []
        for k, v in self._store.items():
            preview = str(v).replace('\n', '\\n')[:80]
            lines.append(f"  {k}: {preview}")

        if self._ns is not None:
            pct = self._ns.get("_context_pct", 0)
            threshold = self._ns.get("_compress_threshold", 50)
            if pct >= threshold:
                lines.append("")
                lines.append(f"⚠ Context {pct}% — consider summarizing old frames then memory.drop(n)")
                lines.append("  print(memory.guide) to see how")

        self.signal = {"entries": "\n".join(lines)} if lines else {}

    def _persist(self) -> None:
        if self._data_dir is None:
            return
        path = self._data_dir / "memory.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._store, f, ensure_ascii=False, indent=2)
        except (OSError, IOError) as e:
            raise RuntimeError(f"Failed to persist memory: {e}") from e

    def _load(self) -> None:
        if self._data_dir is None:
            return
        path = self._data_dir / "memory.json"
        if not path.exists():
            return
        try:
            self._store = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            self._store = {}
