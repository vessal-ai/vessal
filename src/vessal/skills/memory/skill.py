"""skill — Memory Skill implementation."""
import json
from pathlib import Path

from vessal.ark.shell.hull.skill import SkillBase


class Memory(SkillBase):
    """Cross-session key-value memory. Agent calls save/get/delete to manage memory entries.

    Attributes:
        _store: In-memory dict mapping key → value.
        _data_dir: Data directory path; None when no ns is provided.
        _ns: Reference to Hull namespace; None when no ns is provided. Required by drop().
    """

    name = "memory"
    description = "cross-session memory"

    def __init__(self, ns: dict | None = None) -> None:
        """Initialize the Memory skill.

        Args:
            ns: Hull namespace containing the _data_dir path. No persistence without ns.
        """
        super().__init__()
        self._store: dict = {}
        self._ns: dict | None = ns
        self._data_dir: Path | None = None
        if ns is not None:
            base = ns.get("_data_dir")
            if base:
                self._data_dir = Path(base) / "memory"
                self._data_dir.mkdir(parents=True, exist_ok=True)
                self._load()

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
        """Physically delete the oldest n frames from _frame_log. Cold storage is not affected.

        Save key information from old frames with memory.save() before calling this.
        Keeps at least 1 frame. Prints a confirmation prompt before executing deletion.

        Args:
            n: Number of frames to delete.
        """
        if self._ns is None:
            raise RuntimeError("drop() requires a namespace reference; Memory must be initialized with ns")
        if n <= 0:
            return
        frame_log = self._ns.get("_frame_log", [])
        actual = min(n, max(len(frame_log) - 1, 0))
        if actual <= 0:
            print(f"⚠ Frame log only has {len(frame_log)} frame(s); nothing to delete")
            return
        print(
            f"About to delete the oldest {actual} frame(s). Have you saved key information to memory?"
            f" If not, use memory.save() first."
        )
        del frame_log[:actual]
        print(f"Deleted {actual} frame(s) ({len(frame_log)} remaining). Cold storage unaffected.")

    def _signal(self) -> tuple[str, str] | None:
        """Per-frame: output memory entries + context pressure warning."""
        lines = []

        # Memory entries
        for k, v in self._store.items():
            preview = str(v).replace('\n', '\\n')[:80]
            lines.append(f"  {k}: {preview}")

        # Context pressure detection
        if self._ns is not None:
            pct = self._ns.get("_context_pct", 0)
            threshold = self._ns.get("_compress_threshold", 50)
            if pct >= threshold:
                lines.append("")
                lines.append(f"⚠ Context {pct}% — consider summarizing old frames then memory.drop(n)")
                lines.append("  print(memory.guide) to see how")

        if not lines:
            return None
        return ("memory", "\n".join(lines))

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
