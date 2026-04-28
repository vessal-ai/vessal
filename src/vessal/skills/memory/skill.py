"""skill — Memory Skill implementation."""
import json
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
        """Physically delete the oldest n frames from the hot zone. Cold storage is not affected.

        Save key information from old frames with memory.save() before calling this.
        Keeps at least 1 frame in the hot zone. Prints a confirmation before executing.

        Args:
            n: Number of frames to delete.
        """
        if self._ns is None:
            raise RuntimeError("drop() requires a namespace reference; Memory must be initialized with ns")
        if n <= 0:
            return
        fs = self._ns.get("_frame_stream")
        if fs is None:
            print("⚠ No frame stream in namespace; nothing to delete")
            return
        total_hot = fs.hot_frame_count()
        actual = min(n, max(total_hot - 1, 0))
        if actual <= 0:
            print(f"⚠ Hot zone only has {total_hot} frame(s); nothing to delete")
            return
        print(
            f"About to delete the oldest {actual} hot frame(s). Have you saved key information to memory?"
            f" If not, use memory.save() first."
        )
        # Delete from oldest buckets first (B_4..B_0)
        remaining = actual
        for bucket in reversed(fs._hot):
            while bucket and remaining > 0:
                bucket.pop(0)
                remaining -= 1
            if remaining == 0:
                break
        print(f"Deleted {actual} frame(s) ({fs.hot_frame_count()} hot remaining). Cold storage unaffected.")

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
