"""cli.py — Vessal framework-level CLI entry point.

Unified entry point combining runtime commands and development tools.

Runtime commands (require ARK):
  vessal start     Start the Agent server (Shell + Hull + Companions)
  vessal stop      Stop the Agent server
  vessal status    Query Agent status
  vessal once      Single-run mode (--goal required)

Container commands (require Docker):
  vessal build     Build an Agent Docker image
  vessal run       Start an Agent Docker container

Development tools (do not require ARK runtime):
  vessal init      Create project scaffold
  vessal skill     Skill management (init, check)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    """CLI entry point. Called by [project.scripts] in pyproject.toml."""
    parser = argparse.ArgumentParser(
        prog="vessal",
        description="Vessal — Agent Runtime",
    )
    from importlib import metadata as _metadata
    parser.add_argument(
        "--version",
        action="version",
        version=f"vessal {_metadata.version('vessal')}",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ── Runtime commands ──

    # vessal start
    start_parser = subparsers.add_parser("start", help="Start the Agent server")
    start_parser.add_argument("--dir", type=str, default=".", help="Project directory")
    start_parser.add_argument("--port", type=int, default=8420, help="Shell port")
    start_parser.add_argument("--foreground", action="store_true", help="Run in foreground (for debugging)")

    # vessal stop
    stop_parser = subparsers.add_parser("stop", help="Stop the Agent server")
    stop_parser.add_argument("--dir", type=str, default=".", help="Project directory")
    stop_parser.add_argument("--port", type=int, default=8420, help="Shell port")

    # vessal status
    status_parser = subparsers.add_parser("status", help="Query Agent status")
    status_parser.add_argument("--port", type=int, default=8420, help="Shell port")

    # vessal once (single-run mode)
    once_parser = subparsers.add_parser("once", help="Run Agent once (exit after completing one goal)")
    once_parser.add_argument("--goal", type=str, required=True, help="Goal message for the task")
    once_parser.add_argument("--dir", type=str, default=".", help="Project directory")

    # ── Container commands ──

    # vessal build
    build_parser = subparsers.add_parser("build", help="Build an Agent Docker image")
    build_parser.add_argument("agent_dir", nargs="?", default=".", help="Agent project directory")
    build_parser.add_argument("--name", type=str, default=None, help="Image name (defaults to value from hull.toml)")
    build_parser.add_argument("--tag", type=str, default="latest", help="Image tag")

    # vessal run (container mode)
    run_parser = subparsers.add_parser("run", help="Start an Agent Docker container")
    run_parser.add_argument("name", type=str, help="Image/container name")
    run_parser.add_argument("--port", type=int, default=8420, help="Host port")
    run_parser.add_argument("-e", "--env", action="append", default=[], help="Environment variable KEY=VALUE (repeatable)")

    # ── Development tools ──

    # vessal init
    init_parser = subparsers.add_parser("init", help="Create project scaffold")
    init_parser.add_argument("name", type=str, help="Project name")
    init_parser.add_argument(
        "--no-venv", action="store_true",
        help="Skip virtual environment creation and dependency installation"
    )

    # vessal check-update
    subparsers.add_parser("check-update", help="Check PyPI for a newer version")

    # vessal upgrade
    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade vessal to the latest release")
    upgrade_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    # vessal create (interactive wizard)
    create_parser = subparsers.add_parser("create", help="Interactive new-project wizard")
    create_parser.add_argument("name", nargs="?", default=None, help="Project name (skipped in wizard if provided)")

    # vessal skill
    skill_parser = subparsers.add_parser("skill", help="Skill management")
    skill_sub = skill_parser.add_subparsers(dest="skill_command")
    skill_init_parser = skill_sub.add_parser("init", help="Create Skill scaffold")
    skill_init_parser.add_argument("name", type=str, help="Skill name")
    skill_check_parser = skill_sub.add_parser("check", help="Check Skill compliance")
    skill_check_parser.add_argument("path", type=str, help="Path to Skill directory")
    skill_check_parser.add_argument("--test", action="store_true", help="Run tests")

    # vessal skill install
    skill_install_parser = skill_sub.add_parser("install", help="Install a Skill from SkillHub or URL")
    skill_install_parser.add_argument("source", type=str, help="Skill name (SkillHub) or Git URL")
    skill_install_parser.add_argument("-g", "--global", dest="global_install", action="store_true",
                                      help="Install to user-level (~/.vessal/skills/)")

    # vessal skill uninstall
    skill_uninstall_parser = skill_sub.add_parser("uninstall", help="Uninstall a hub-installed Skill")
    skill_uninstall_parser.add_argument("name", type=str, help="Skill name to uninstall")
    skill_uninstall_parser.add_argument("-g", "--global", dest="global_install", action="store_true",
                                         help="Uninstall from user-level (~/.vessal/skills/)")

    # vessal skill update
    skill_update_parser = skill_sub.add_parser("update", help="Update hub-installed Skills")
    skill_update_parser.add_argument("name", nargs="?", default=None, help="Skill name (omit to update all)")

    # vessal skill search
    skill_search_parser = skill_sub.add_parser("search", help="Search SkillHub registry")
    skill_search_parser.add_argument("keyword", type=str, help="Search keyword")

    # vessal skill list
    skill_list_parser = skill_sub.add_parser("list", help="List available Skills")
    skill_list_parser.add_argument("--installed", action="store_true", help="Only show hub-installed Skills")

    # vessal skill publish
    skill_publish_parser = skill_sub.add_parser("publish", help="Submit Skill to SkillHub")
    skill_publish_parser.add_argument("path", type=str, help="Path to Skill directory")

    args = parser.parse_args()

    from vessal.ark.shell.errors import CliUserError

    try:
        if args.command == "start":
            _cmd_start(args)
        elif args.command == "stop":
            _cmd_stop(args)
        elif args.command == "status":
            _cmd_status(args)
        elif args.command == "once":
            _cmd_once(args)
        elif args.command == "build":
            _cmd_build(args)
        elif args.command == "run":
            _cmd_container_run(args)
        elif args.command == "init":
            _cmd_init(args)
        elif args.command == "check-update":
            _cmd_check_update()
        elif args.command == "upgrade":
            _cmd_upgrade(args)
        elif args.command == "create":
            from vessal.ark.shell.tui.create_wizard import run as wizard_run
            sys.exit(wizard_run(Path.cwd()))
        elif args.command == "skill":
            if args.skill_command == "init":
                _cmd_skill_init(args)
            elif args.skill_command == "check":
                _cmd_skill_check(args)
            elif args.skill_command == "install":
                _cmd_skill_install(args)
            elif args.skill_command == "uninstall":
                _cmd_skill_uninstall(args)
            elif args.skill_command == "update":
                _cmd_skill_update(args)
            elif args.skill_command == "search":
                _cmd_skill_search(args)
            elif args.skill_command == "list":
                _cmd_skill_list(args)
            elif args.skill_command == "publish":
                _cmd_skill_publish(args)
            else:
                skill_parser.print_help()
                sys.exit(1)
        else:
            if args.command is None:
                from vessal.ark.shell.tui.picker import run as picker_run
                sys.exit(picker_run(Path.cwd()))
            parser.print_help()
            sys.exit(1)
    except CliUserError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


# ── Runtime command implementations ──

def _cmd_start(args: argparse.Namespace) -> None:
    """Start the Agent server and Companion processes."""
    from vessal.ark.shell.cli.process_cmds import _cmd_start as shell_start
    shell_start(args)


def _cmd_stop(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli.process_cmds import _cmd_stop as shell_stop
    shell_stop(args)


def _cmd_status(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli.process_cmds import _cmd_status as shell_status
    shell_status(args)


def _cmd_once(args: argparse.Namespace) -> None:
    """Run Agent in single-run mode.

    Does not start the Shell HTTP server. Creates a Hull directly, injects
    the goal message, runs one wake cycle, then exits.
    """
    import asyncio

    project_dir = Path(args.dir).resolve()
    if not (project_dir / "hull.toml").exists():
        print(f"Error: {project_dir} is not a Vessal project (hull.toml not found).", file=sys.stderr)
        sys.exit(1)

    from vessal.ark.shell.hull.hull import Hull
    hull = Hull(str(project_dir))

    # Inject goal into the chat skill inbox (if loaded)
    chat = hull._cell.ns.get("chat")
    if chat is not None and hasattr(chat, "receive"):
        chat.receive(args.goal)
    hull.wake("user_message")

    try:
        asyncio.run(hull.run_once())
    except KeyboardInterrupt:
        print("\nInterrupted.")


def _cmd_build(args: argparse.Namespace) -> None:
    """Build an Agent Docker image."""
    from vessal.ark.shell.runtime.container.build import build_image

    agent_dir = Path(args.agent_dir).resolve()
    if not (agent_dir / "hull.toml").exists():
        print(f"Error: {agent_dir} is not a Vessal project (hull.toml not found).", file=sys.stderr)
        sys.exit(1)

    build_image(agent_dir, name=args.name, tag=args.tag)


def _cmd_container_run(args: argparse.Namespace) -> None:
    """Start an Agent Docker container."""
    from vessal.ark.shell.runtime.container.build import run_container

    env = {}
    for item in args.env:
        if "=" in item:
            k, v = item.split("=", 1)
            env[k] = v
        else:
            print(f"Warning: ignoring invalid environment variable format (expected KEY=VALUE): {item!r}", file=sys.stderr)
    run_container(name=args.name, port=args.port, env=env or None)


# ── Development tool implementations ──

def _cmd_init(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli.init_cmds import _cmd_init as shell_init
    shell_init(args)


def _cmd_skill_init(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli.skill_cmds import _cmd_skill_init as shell_skill_init
    shell_skill_init(args)


def _cmd_skill_check(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli.skill_cmds import _cmd_skill_check as shell_skill_check
    shell_skill_check(args)


def _cmd_skill_install(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli.skill_cmds import _cmd_skill_install as shell_skill_install
    shell_skill_install(args)


def _cmd_skill_uninstall(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli.skill_cmds import _cmd_skill_uninstall as shell_skill_uninstall
    shell_skill_uninstall(args)


def _cmd_skill_update(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli.skill_cmds import _cmd_skill_update as shell_skill_update
    shell_skill_update(args)


def _cmd_skill_search(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli.skill_cmds import _cmd_skill_search as shell_skill_search
    shell_skill_search(args)


def _cmd_skill_list(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli.skill_cmds import _cmd_skill_list as shell_skill_list
    shell_skill_list(args)


def _cmd_skill_publish(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli.skill_cmds import _cmd_skill_publish as shell_skill_publish
    shell_skill_publish(args)


def _cmd_check_update() -> None:
    """Check PyPI for a newer vessal version."""
    from importlib import metadata
    from vessal.ark.shell.cli import upgrade

    current = metadata.version("vessal")
    try:
        latest = upgrade.check_pypi_latest("vessal")
    except Exception as e:
        print(f"Error: could not reach PyPI ({e})", file=sys.stderr)
        sys.exit(1)

    if upgrade.is_newer(latest, current=current):
        print(f"Update available: {current} -> {latest}")
        print(f"Run 'vessal upgrade' to install.")
    else:
        print(f"vessal {current} is up to date.")


def _cmd_upgrade(args: argparse.Namespace) -> None:
    """Detect installer (uv / pipx / pip) and run the matching upgrade command."""
    import subprocess
    from importlib import metadata
    from vessal.ark.shell.cli import upgrade

    current = metadata.version("vessal")
    try:
        latest = upgrade.check_pypi_latest("vessal")
    except Exception as e:
        print(f"Error: could not reach PyPI ({e})", file=sys.stderr)
        sys.exit(1)

    if not upgrade.is_newer(latest, current=current):
        print(f"vessal {current} is up to date.")
        return

    installer = upgrade.detect_installer()
    cmd = upgrade.build_upgrade_cmd(installer)
    print(f"Upgrading vessal {current} -> {latest} (via {installer}):")
    print(f"  $ {' '.join(cmd)}")

    if not args.yes:
        try:
            ans = input("Proceed? [Y/n] ").strip().lower()
        except EOFError:
            ans = ""
        if ans in ("n", "no"):
            print("Aborted.")
            return

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
