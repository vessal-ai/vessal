"""skills_manifest.py — Declarative Skill list written alongside cloudpickle snapshots.

Hull writes this before `cell.snapshot()` and reads it before `cell.restore()`.
Kernel remains oblivious; it only handles ns bytes.
"""
from __future__ import annotations
import json
from pathlib import Path


def write_manifest(path: Path | str, loaded: dict[str, dict]) -> None:
    Path(path).write_text(json.dumps(loaded, ensure_ascii=False, indent=2), encoding="utf-8")


def read_manifest(path: Path | str) -> dict[str, dict]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))
