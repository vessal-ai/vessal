# src/vessal/ark/shell/hub/installer.py
"""Clone, locate, validate, and copy skills from git repos."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from vessal.ark.shell.hub.metadata import write_installed
from vessal.ark.shell.hub.resolver import ResolvedSource


def locate_skill_in_repo(repo_dir: Path, subpath: str | None) -> Path:
    """Locate the skill directory within a cloned repo.

    Convention-over-scanning rules:
    1. If subpath is given, return repo_dir/subpath (must contain SKILL.md).
    2. If root has SKILL.md, root is the skill.
    3. If root has skills/ subdirectory, return that (monorepo mode).
    4. Otherwise, error.

    For monorepo without subpath, returns the skills/ directory itself
    (the caller should list children to find individual skills).
    """
    if subpath:
        target = repo_dir / subpath
        if not target.is_dir() or not (target / "SKILL.md").exists():
            raise RuntimeError(
                f"Skill not found at subpath '{subpath}' in repository. "
                f"Expected SKILL.md at {target}"
            )
        return target

    if (repo_dir / "SKILL.md").exists():
        return repo_dir

    skills_dir = repo_dir / "skills"
    if skills_dir.is_dir():
        return skills_dir

    raise RuntimeError(
        f"Cannot locate skill in repository {repo_dir}. "
        f"Expected SKILL.md at root or a skills/ subdirectory."
    )


def copy_skill(source_dir: Path, target_base: Path, name: str) -> Path:
    """Copy a skill directory to the target location, overwriting if exists."""
    dest = target_base / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        str(source_dir),
        str(dest),
        ignore=shutil.ignore_patterns("__pycache__", ".git"),
    )
    return dest


def clone_repo(git_url: str) -> Path:
    """Clone a git repo to a temporary directory. Returns the repo path."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="vessal_install_"))
    subprocess.run(
        ["git", "clone", "--depth", "1", git_url, str(tmp_dir / "repo")],
        check=True,
        capture_output=True,
        text=True,
    )
    return tmp_dir / "repo"


def install(
    resolved: ResolvedSource,
    target_dir: Path,
) -> str:
    """Full install flow: clone, locate, validate, copy, write metadata.

    Args:
        resolved: Resolved source with git_url, subpath, verified flag.
        target_dir: Directory to install into (e.g. project skills/hub/).

    Returns:
        Success message string.
    """
    from vessal.ark.shell.hull.skill_manager import _parse_skill_md

    if not resolved.verified:
        print(
            "\n  WARNING: This skill is from an unverified source.\n"
            "  Review the source code before using it.\n"
            f"  Source: {resolved.original}\n",
            file=sys.stderr,
        )

    repo_dir = clone_repo(resolved.git_url)

    try:
        skill_location = locate_skill_in_repo(repo_dir, resolved.subpath)

        if (skill_location / "SKILL.md").exists():
            # Single skill
            meta, _ = _parse_skill_md(skill_location / "SKILL.md")
            name = meta.get("name", skill_location.name)
            version = meta.get("version", "0.0.0")

            target_dir.mkdir(parents=True, exist_ok=True)
            dest = copy_skill(skill_location, target_dir, name)
            write_installed(dest, source=resolved.original, version=version, verified=resolved.verified)
            return f"Installed {name} v{version}"
        else:
            # Monorepo: scan for skills with SKILL.md
            installed = []
            for child in sorted(skill_location.iterdir()):
                if child.is_dir() and (child / "SKILL.md").exists():
                    meta, _ = _parse_skill_md(child / "SKILL.md")
                    name = meta.get("name", child.name)
                    version = meta.get("version", "0.0.0")

                    target_dir.mkdir(parents=True, exist_ok=True)
                    dest = copy_skill(child, target_dir, name)
                    write_installed(dest, source=resolved.original, version=version, verified=resolved.verified)
                    installed.append(f"{name} v{version}")

            if not installed:
                raise RuntimeError(f"No skills found in {skill_location}")
            return f"Installed: {', '.join(installed)}"
    finally:
        shutil.rmtree(repo_dir.parent, ignore_errors=True)
