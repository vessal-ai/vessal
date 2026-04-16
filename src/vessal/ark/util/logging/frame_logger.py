"""frame_logger.py — JSONL frame log writer; all runs append to the same frames.jsonl."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import IO

logger = logging.getLogger(__name__)


class FrameLogger:
    """JSONL frame log writer. All runs append to the same frames.jsonl.

    Attributes:
        _log_dir: Path to the log directory.
        _file: Currently open file object.
        _path: Full path to frames.jsonl.
    """

    def __init__(self, log_dir: str | Path) -> None:
        """Initialize the writer.

        Args:
            log_dir: Log directory (frames.jsonl will be created here).
        """
        self._log_dir = Path(log_dir)
        self._file: IO[str] | None = None
        self._path: Path | None = None

    def open(self) -> Path:
        """Open frames.jsonl in append mode and return the file path.

        Returns:
            Full path to frames.jsonl.
        """
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._log_dir / "frames.jsonl"
        self._file = open(self._path, "a", encoding="utf-8")
        return self._path

    def write_frame(self, frame: dict) -> None:
        """Write one frame record.

        Args:
            frame: Frame dict or an object with a to_dict() method.

        Raises:
            RuntimeError: Called before open().
        """
        if self._file is None:
            raise RuntimeError("FrameLogger.write_frame() called before open()")
        frame_dict = frame if isinstance(frame, dict) else frame.to_dict()
        line = json.dumps(frame_dict, ensure_ascii=False)
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        """Close the file."""
        if self._file is not None:
            self._file.close()
            self._file = None

    @property
    def raw_jsonl_path(self) -> Path | None:
        """Full path to frames.jsonl, or None if not yet opened.

        Returns:
            File path or None.
        """
        return self._path
