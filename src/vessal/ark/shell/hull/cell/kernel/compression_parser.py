"""compression_parser.py — Parse LLM compression output into CompactionRecord.

Called by the Hull compression worker after compression_core.step().
"""
from __future__ import annotations

import json
import re

from vessal.ark.shell.hull.cell.protocol import CompactionRecord


class CompactionParseError(ValueError):
    """Raised when LLM compression output cannot be parsed into schema v1."""


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?|\n?```\s*$", re.MULTILINE)

_REQUIRED_FIELDS = ("range", "intent", "operations", "outcomes", "artifacts", "notable")


def parse_compaction_json(raw: str, *, layer: int, compacted_at: int) -> CompactionRecord:
    """Extract and validate the LLM's JSON output; return a CompactionRecord.

    Raises:
        CompactionParseError on any validation failure.
    """
    stripped = _FENCE_RE.sub("", raw.strip())
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise CompactionParseError(f"invalid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise CompactionParseError(f"expected JSON object, got {type(payload).__name__}")
    for field in _REQUIRED_FIELDS:
        if field not in payload:
            raise CompactionParseError(f"missing required field: {field}")
    range_ = payload["range"]
    if not (isinstance(range_, list) and len(range_) == 2
            and all(isinstance(x, int) for x in range_)):
        raise CompactionParseError(f"range must be [int, int], got {range_!r}")
    ops = payload["operations"]
    arts = payload["artifacts"]
    if not isinstance(ops, list) or not all(isinstance(x, str) for x in ops):
        raise CompactionParseError("operations must be list[str]")
    if not isinstance(arts, list) or not all(isinstance(x, str) for x in arts):
        raise CompactionParseError("artifacts must be list[str]")
    return CompactionRecord(
        range=(range_[0], range_[1]),
        intent=str(payload["intent"]),
        operations=tuple(ops[:4]),
        outcomes=str(payload["outcomes"]),
        artifacts=tuple(arts[:4]),
        notable=str(payload["notable"]),
        layer=layer,
        compacted_at=compacted_at,
    )
