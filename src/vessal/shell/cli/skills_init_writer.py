"""Write and maintain <project>/skills/__init__.py — the central Skill registry.

Each line: `from .<folder> import <ClassName>`. ClassName is the PascalCase of
the folder name. The registry is alphabetically sorted; this is enforced on
every add / remove so diffs stay readable.
"""
from __future__ import annotations

from pathlib import Path


def _camel(snake: str) -> str:
    return "".join(part.capitalize() for part in snake.split("_") if part)


def _read_folders(skills_dir: Path) -> list[str]:
    """Read the current registry; return the list of folder names it imports from."""
    init = skills_dir / "__init__.py"
    if not init.exists():
        return []
    folders: list[str] = []
    for line in init.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("from .") and " import " in line:
            folder = line.split()[1].lstrip(".")
            folders.append(folder)
    return folders


def _write(skills_dir: Path, folders: list[str]) -> None:
    """Rewrite skills/__init__.py with the given folders, alphabetized."""
    folders = sorted(set(folders))
    classes = [_camel(f) for f in folders]
    lines = ['"""Project Skills package — central registry, written by vessal create."""']
    for folder, cls in zip(folders, classes):
        lines.append(f"from .{folder} import {cls}")
    lines.append("")
    lines.append(f"__all__ = [{', '.join(f'{chr(34)}{c}{chr(34)}' for c in classes)}]")
    lines.append("")
    (skills_dir / "__init__.py").write_text("\n".join(lines), encoding="utf-8")


def write_initial(skills_dir: Path, folders: list[str]) -> None:
    """Bootstrap call: create skills/__init__.py from the given list."""
    _write(skills_dir, folders)


def add(skills_dir: Path, folder: str) -> None:
    """Append a folder to the registry (idempotent)."""
    folders = _read_folders(skills_dir)
    if folder in folders:
        return
    folders.append(folder)
    _write(skills_dir, folders)


def remove(skills_dir: Path, folder: str) -> None:
    """Drop a folder from the registry (idempotent)."""
    folders = _read_folders(skills_dir)
    if folder not in folders:
        return
    folders = [f for f in folders if f != folder]
    _write(skills_dir, folders)
