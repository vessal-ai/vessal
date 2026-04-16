"""cli.py — Vessal framework-level CLI entry point.

Unified entry point combining runtime commands and development tools.

Runtime commands (require ARK):
  vessal start     Start the Agent server (Shell + Hull + Companions)
  vessal stop      Stop the Agent server
  vessal status    Query Agent status
  vessal send      Send a message to the Agent inbox
  vessal read      Read Agent replies
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

    # vessal send
    send_parser = subparsers.add_parser("send", help="Send a message to the Agent inbox")
    send_parser.add_argument("message", type=str, help="Message content")
    send_parser.add_argument("--port", type=int, default=8420, help="Shell port")

    # vessal read
    read_parser = subparsers.add_parser("read", help="Read Agent replies")
    read_parser.add_argument("--port", type=int, default=8420, help="Shell port")
    read_parser.add_argument("--wait", type=float, default=0, help="Seconds to wait")

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

    # vessal skill
    skill_parser = subparsers.add_parser("skill", help="Skill management")
    skill_sub = skill_parser.add_subparsers(dest="skill_command")
    skill_init_parser = skill_sub.add_parser("init", help="Create Skill scaffold")
    skill_init_parser.add_argument("name", type=str, help="Skill name")
    skill_check_parser = skill_sub.add_parser("check", help="Check Skill compliance")
    skill_check_parser.add_argument("path", type=str, help="Path to Skill directory")
    skill_check_parser.add_argument("--test", action="store_true", help="Run tests")

    args = parser.parse_args()

    if args.command == "start":
        _cmd_start(args)
    elif args.command == "stop":
        _cmd_stop(args)
    elif args.command == "status":
        _cmd_status(args)
    elif args.command == "send":
        _cmd_send(args)
    elif args.command == "read":
        _cmd_read(args)
    elif args.command == "once":
        _cmd_once(args)
    elif args.command == "build":
        _cmd_build(args)
    elif args.command == "run":
        _cmd_container_run(args)
    elif args.command == "init":
        _cmd_init(args)
    elif args.command == "skill":
        if args.skill_command == "init":
            _cmd_skill_init(args)
        elif args.skill_command == "check":
            _cmd_skill_check(args)
        else:
            skill_parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


# ── Runtime command implementations ──

def _cmd_start(args: argparse.Namespace) -> None:
    """Start the Agent server and Companion processes."""
    from vessal.ark.shell.cli import _cmd_start as shell_start
    shell_start(args)


def _cmd_stop(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli import _cmd_stop as shell_stop
    shell_stop(args)


def _cmd_status(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli import _cmd_status as shell_status
    shell_status(args)


def _cmd_send(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli import _cmd_send as shell_send
    shell_send(args)


def _cmd_read(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli import _cmd_read as shell_read
    shell_read(args)


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
    from vessal.ark.shell.container.build import build_image

    agent_dir = Path(args.agent_dir).resolve()
    if not (agent_dir / "hull.toml").exists():
        print(f"Error: {agent_dir} is not a Vessal project (hull.toml not found).", file=sys.stderr)
        sys.exit(1)

    build_image(agent_dir, name=args.name, tag=args.tag)


def _cmd_container_run(args: argparse.Namespace) -> None:
    """Start an Agent Docker container."""
    from vessal.ark.shell.container.build import run_container

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
    from vessal.ark.shell.cli import _cmd_init as shell_init
    shell_init(args)


def _cmd_skill_init(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli import _cmd_skill_init as shell_skill_init
    shell_skill_init(args)


def _cmd_skill_check(args: argparse.Namespace) -> None:
    from vessal.ark.shell.cli import _cmd_skill_check as shell_skill_check
    shell_skill_check(args)
