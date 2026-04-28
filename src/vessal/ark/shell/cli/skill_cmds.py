"""skill_cmds.py — Skill management CLI command implementations."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vessal.ark.shell.cli.scaffold import write_skill_scaffold


def _cmd_skill_create(args: argparse.Namespace) -> None:
    """Run the skill-create wizard and scaffold the chosen Skill."""
    from vessal.ark.shell.tui.skill_create_wizard import run_skill_create_wizard

    choices = run_skill_create_wizard()
    base = Path(choices.name)
    if base.exists():
        print(f"Error: directory {base} already exists.", file=sys.stderr)
        sys.exit(1)
    write_skill_scaffold(
        base,
        choices.name,
        with_tutorial=choices.with_tutorial,
        with_ui=choices.with_ui,
        with_server=choices.with_server,
    )
    print(f"Skill '{choices.name}' scaffold created at ./{choices.name}/")


def _cmd_skill_check(args: argparse.Namespace) -> None:
    """Check Skill directory compliance.

    Checks __init__.py, skill.py, SKILL.md, and BaseSkill inheritance.
    With --test, additionally runs tests/ directory.
    Exits with code 1 if any FAIL; exits with code 0 if only WARNs.
    """
    import importlib
    import subprocess

    from vessal.ark.shell.hull.skill_loader import _parse_skill_md as parse_skill_md

    skill_dir = Path(args.path).resolve()
    name = skill_dir.name

    errors: list[str] = []
    warnings: list[str] = []

    def ok(msg: str) -> None:
        print(f"[OK]   {msg}")

    def warn(msg: str) -> None:
        print(f"[WARN] {msg}")
        warnings.append(msg)

    def fail(msg: str) -> None:
        print(f"[FAIL] {msg}")
        errors.append(msg)

    print(f"Checking Skill: {name} ({skill_dir})\n")

    # 1. Directory exists
    if not skill_dir.is_dir():
        fail(f"Directory not found: {skill_dir}")
        print(f"\nResult: 1 error, 0 warnings")
        sys.exit(1)

    # 2. __init__.py must exist
    init_py = skill_dir / "__init__.py"
    if init_py.exists():
        ok("__init__.py exists")
    else:
        fail("__init__.py not found")

    # 3. skill.py must exist
    skill_py = skill_dir / "skill.py"
    if skill_py.exists():
        ok("skill.py exists")
    else:
        fail("skill.py not found")

    # 4. SKILL.md recommended
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        ok("SKILL.md exists")
        meta, _body = parse_skill_md(skill_md)
        for field in ("name", "description"):
            val = meta.get(field, "")
            if val:
                ok(f"  SKILL.md[{field}]: {val}")
            else:
                warn(f"SKILL.md missing {field} field")

        # v1 field checks
        for field in ("version", "author", "license"):
            val = meta.get(field, "")
            if val:
                ok(f"  SKILL.md[{field}]: {val}")
            else:
                warn(f"SKILL.md missing {field} field (recommended for distribution)")

        # requires.skills check
        requires = meta.get("requires", {})
        if isinstance(requires, dict):
            req_skills = requires.get("skills", [])
            if isinstance(req_skills, list):
                ok(f"  requires.skills: {req_skills}")
            else:
                warn("SKILL.md requires.skills should be a list")
    else:
        warn("SKILL.md not found (recommended)")

    # 5. Module import + BaseSkill check
    if init_py.exists():
        parent_str = str(skill_dir.parent)
        added = parent_str not in sys.path
        if added:
            sys.path.insert(0, parent_str)
        try:
            # Clear any stale sys.modules cache
            stale = [k for k in sys.modules if k == name or k.startswith(name + ".")]
            for k in stale:
                del sys.modules[k]
            module = importlib.import_module(name)
            ok("Module imported successfully")

            skill_cls = getattr(module, "Skill", None)
            if skill_cls is None:
                fail("__init__.py does not export 'Skill' (should be: from .skill import XxxClass as Skill)")
            else:
                ok("Exports 'Skill'")
                from vessal.skills._base import BaseSkill
                if issubclass(skill_cls, BaseSkill):
                    ok(f"Skill inherits BaseSkill: {skill_cls.__name__}")
                else:
                    fail(f"Skill {skill_cls.__name__!r} does not inherit BaseSkill")

                if isinstance(getattr(skill_cls, "name", None), str):
                    ok(f"  name = {skill_cls.name!r}")
                else:
                    fail("Skill missing name class attribute")

                if isinstance(getattr(skill_cls, "description", None), str):
                    ok(f"  description = {skill_cls.description!r}")
                else:
                    fail("Skill missing description class attribute")

        except Exception as e:
            fail(f"Module import failed: {e}")
        finally:
            if added and parent_str in sys.path:
                sys.path.remove(parent_str)

    # 6. Optional tests
    if args.test:
        tests_dir = skill_dir / "tests"
        if tests_dir.is_dir():
            print("\nRunning tests...")
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(tests_dir), "-q"],
            )
            if result.returncode != 0:
                fail("Tests failed")
        else:
            warn("tests/ directory not found, skipping tests")

    # Summary
    print()
    if not errors and not warnings:
        print("Result: passed, no issues")
    else:
        parts = []
        if errors:
            parts.append(f"{len(errors)} error(s)")
        if warnings:
            parts.append(f"{len(warnings)} warning(s)")
        print(f"Result: {', '.join(parts)}")

    if errors:
        sys.exit(1)


def _cmd_skill_install(args: argparse.Namespace) -> None:
    """Install a Skill from SkillHub (by name) or from a Git URL."""
    from vessal.ark.shell.hull.hub.resolver import resolve
    from vessal.ark.shell.hull.hub.installer import install

    source = args.source
    global_install = getattr(args, "global_install", False)

    if global_install:
        target_dir = Path.home() / ".vessal" / "skills"
    else:
        target_dir = Path.cwd() / "skills" / "hub"

    try:
        resolved = resolve(source)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        result = install(resolved, target_dir)
        print(f"\n  {result}")
        if resolved.verified:
            print(f"  Source: SkillHub ({resolved.original})")
        else:
            print(f"  Source: {resolved.original} (unverified)")
        print(f"  Location: {target_dir}")
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_skill_uninstall(args: argparse.Namespace) -> None:
    """Uninstall a hub-installed Skill by removing its directory."""
    import shutil

    name = args.name
    global_install = getattr(args, "global_install", False)

    if global_install:
        skill_dir = Path.home() / ".vessal" / "skills" / name
    else:
        skill_dir = Path.cwd() / "skills" / "hub" / name

    if not skill_dir.is_dir():
        print(f"Error: Skill '{name}' not found at {skill_dir}", file=sys.stderr)
        sys.exit(1)

    from vessal.ark.shell.hull.hub.metadata import is_hub_installed
    if not is_hub_installed(skill_dir) and not global_install:
        print(f"Error: '{name}' is not a hub-installed skill (no .installed.toml)", file=sys.stderr)
        sys.exit(1)

    shutil.rmtree(skill_dir)
    print(f"Uninstalled {name}")


def _cmd_skill_update(args: argparse.Namespace) -> None:
    """Update hub-installed Skills by re-fetching from their original source."""
    from vessal.ark.shell.hull.hub.metadata import read_installed
    from vessal.ark.shell.hull.hub.resolver import resolve
    from vessal.ark.shell.hull.hub.installer import install
    from vessal.ark.shell.hull.skill_loader import _parse_skill_md

    hub_dir = Path.cwd() / "skills" / "hub"
    if not hub_dir.is_dir():
        print("No hub-installed skills found.", file=sys.stderr)
        sys.exit(1)

    targets = []
    if args.name:
        skill_dir = hub_dir / args.name
        if not skill_dir.is_dir():
            print(f"Error: Skill '{args.name}' not found in {hub_dir}", file=sys.stderr)
            sys.exit(1)
        targets.append(skill_dir)
    else:
        for child in sorted(hub_dir.iterdir()):
            if child.is_dir() and (child / ".installed.toml").exists():
                targets.append(child)

    if not targets:
        print("No hub-installed skills to update.")
        return

    for skill_dir in targets:
        meta_installed = read_installed(skill_dir)
        if meta_installed is None:
            continue

        source = meta_installed["source"]
        local_version = meta_installed.get("version", "0.0.0")
        name = skill_dir.name

        try:
            resolved = resolve(source)
            result = install(resolved, hub_dir)
            new_meta, _ = _parse_skill_md(skill_dir / "SKILL.md")
            new_version = new_meta.get("version", "0.0.0")
            if new_version != local_version:
                print(f"  Updated {name}: {local_version} -> {new_version}")
            else:
                print(f"  {name} already at latest ({local_version})")
        except Exception as e:
            print(f"  Failed to update {name}: {e}", file=sys.stderr)


def _cmd_skill_search(args: argparse.Namespace) -> None:
    """Search the SkillHub registry by keyword."""
    from vessal.ark.shell.hull.hub.registry import Registry

    try:
        registry = Registry.fetch()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    results = registry.search(args.keyword)
    if not results:
        print(f"No skills found matching '{args.keyword}'")
        return

    print(f"Found {len(results)} skill(s):\n")
    for entry in results:
        tags = ", ".join(entry.get("tags", []))
        print(f"  {entry['name']}")
        print(f"    {entry.get('description', '')}")
        if tags:
            print(f"    tags: {tags}")
        print(f"    install: vessal skill install {entry['name']}")
        print()


def _cmd_skill_list(args: argparse.Namespace) -> None:
    """List available Skills, grouped by source directory."""
    from vessal.ark.shell.hull.hub.metadata import read_installed
    from vessal.ark.shell.hull.skill_loader import _parse_skill_md

    cwd = Path.cwd()
    sections = []

    if args.installed:
        hub_dir = cwd / "skills" / "hub"
        global_dir = Path.home() / ".vessal" / "skills"
        for label, base in [("Project (skills/hub)", hub_dir), ("Global (~/.vessal/skills)", global_dir)]:
            if not base.is_dir():
                continue
            skills = []
            for child in sorted(base.iterdir()):
                if not child.is_dir():
                    continue
                meta = read_installed(child)
                if meta is None:
                    continue
                skills.append((child.name, meta.get("version", "?"), meta.get("source", "?"),
                              "verified" if meta.get("verified") else "unverified"))
            if skills:
                sections.append((label, skills))
    else:
        for label, dirname in [("Bundled", "skills/bundled"), ("Hub", "skills/hub"), ("Local", "skills/local")]:
            base = cwd / dirname
            if not base.is_dir():
                continue
            skills = []
            for child in sorted(base.iterdir()):
                if not child.is_dir() or child.name.startswith("_"):
                    continue
                md = child / "SKILL.md"
                if md.exists():
                    meta, _ = _parse_skill_md(md)
                    skills.append((meta.get("name", child.name), meta.get("version", "?"),
                                  meta.get("description", "")))
                else:
                    skills.append((child.name, "?", "(no SKILL.md)"))
            if skills:
                sections.append((label, skills))

    if not sections:
        print("No skills found.")
        return

    for label, skills in sections:
        print(f"\n  {label}:")
        for skill_info in skills:
            if len(skill_info) == 4:
                name, version, source, verified = skill_info
                print(f"    {name} v{version} ({verified}) from {source}")
            else:
                name, version, desc = skill_info
                print(f"    {name} v{version} — {desc}")
    print()


def _cmd_skill_publish(args: argparse.Namespace) -> None:
    """Guide user to submit a Skill to the SkillHub curated registry."""
    import webbrowser

    from vessal.ark.shell.hull.skill_loader import _parse_skill_md

    skill_dir = Path(args.path).resolve()
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        print(f"Error: SKILL.md not found in {skill_dir}", file=sys.stderr)
        sys.exit(1)

    meta, _ = _parse_skill_md(skill_md)
    name = meta.get("name", skill_dir.name)

    print(f"Running compliance check on '{name}'...")
    _cmd_skill_check(argparse.Namespace(path=str(skill_dir), test=False))

    print(f"\n  To publish '{name}' to SkillHub:")
    print(f"  1. Push your skill to a public Git repository")
    print(f"  2. Open a PR to vessal-ai/vessal-skills adding an entry to registry.toml:")
    print(f"")
    print(f'     [{name}]')
    print(f'     source = "your-username/your-repo"')
    print(f'     description = "{meta.get("description", "")}"')
    print(f'     tags = []')
    print(f"")

    url = "https://github.com/vessal-ai/vessal-skills/edit/main/registry.toml"
    print(f"  Opening: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        print(f"  (Could not open browser. Visit the URL manually.)")
