"""reader.py — Canonical JSONL log reader; parses frame records written by FrameLogger."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from vessal.ark.shell.hull.cell.protocol import FrameRecord

logger = logging.getLogger(__name__)

# Legacy format (v2) marker keys: if these keys are present but schema_version is absent, treat as legacy.
_LEGACY_KEYS = {"state", "action"}


def _is_legacy(data: dict) -> bool:
    """Detect whether a line is in the legacy (v2) format.

    Legacy format: contains a 'state' or 'action' key but no 'schema_version' key.

    Args:
        data: Dictionary parsed from a JSONL line.

    Returns:
        True if the line is in the legacy format and should raise ValueError.
    """
    has_legacy_key = bool(_LEGACY_KEYS & data.keys())
    has_schema = "schema_version" in data
    return has_legacy_key and not has_schema


def read_frames(path: str) -> list[FrameRecord]:
    """Read a canonical JSONL file and return a list of FrameRecord objects.

    Only accepts canonical format (with schema_version). Legacy format (with 'state' or 'action'
    keys but without schema_version) raises ValueError with the file path and line number.

    Args:
        path: Path string to the JSONL file.

    Returns:
        List of FrameRecord objects in file-line order. Returns empty list for empty files.

    Raises:
        ValueError: A legacy-format line was detected, or FrameRecord.from_dict() failed.
            Error message format: "{path}:{line_no}: <reason>"
    """
    file_path = Path(path)
    results: list[FrameRecord] = []
    text = file_path.read_text(encoding="utf-8")
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: JSON parse failed: {exc}") from exc
        if _is_legacy(data):
            raise ValueError(
                f"{path}:{line_no}: Legacy format detected (contains 'state'/'action' but no "
                f"'schema_version'). Please regenerate the log in canonical format."
            )
        try:
            record = FrameRecord.from_dict(data)
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"{path}:{line_no}: FrameRecord parse failed: {exc}") from exc
        results.append(record)
    return results
