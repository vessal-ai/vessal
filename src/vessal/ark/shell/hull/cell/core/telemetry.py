"""telemetry.py — Per-Cell JSONL telemetry writer for token + cache hit metrics.

One line per LLM call appended to <cell_data_dir>/cache_metrics.jsonl. Pure
function: takes a path and a record dict; opens, appends, closes. No state.
"""
from __future__ import annotations

import json
from pathlib import Path


def append_usage(jsonl_path: str | Path, record: dict) -> None:
    """Append one JSON line to jsonl_path.

    Creates the file if absent. Parent directory must already exist —
    Cell guarantees this via the data_dir invariant.

    Each call opens / writes / closes — telemetry frequency is the LLM
    call rate (~once per second at most), low enough that per-call open
    is fine.
    """
    line = json.dumps(record, ensure_ascii=False)
    with open(jsonl_path, "a", encoding="utf-8") as f:
        f.write(line)
        f.write("\n")
