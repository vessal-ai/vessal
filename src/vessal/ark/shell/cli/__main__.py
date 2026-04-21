"""__main__.py — Vessal CLI dispatch."""
from __future__ import annotations

import argparse
import sys

from vessal.ark.shell.cli.process_cmds import _cmd_start, _cmd_stop, _cmd_status
from vessal.ark.shell.cli.skill_cmds import (
    _cmd_skill_create,
    _cmd_skill_check,
    _cmd_skill_install,
    _cmd_skill_uninstall,
    _cmd_skill_update,
    _cmd_skill_search,
    _cmd_skill_list,
    _cmd_skill_publish,
)

def main() -> None:
    """CLI entry function. Called by pyproject.toml [project.scripts]."""
    parser = argparse.ArgumentParser(
        prog="vessal",
        description="Vessal Agent runtime",
    )
    subparsers = parser.add_subparsers(dest="command")

    # vessal start
    start_parser = subparsers.add_parser("start", help="Start Agent server")
    start_parser.add_argument(
        "--dir", type=str, default=".",
        help="Project directory (default: current directory)",
    )
    start_parser.add_argument(
        "--port", type=int, default=8420,
        help="Listen port (default: 8420)",
    )
    start_parser.add_argument(
        "--daemon", "-d", action="store_true",
        help="Run in background (default: foreground)",
    )

    # vessal stop
    stop_parser = subparsers.add_parser("stop", help="Stop Agent server")
    stop_parser.add_argument(
        "--dir", type=str, default=".",
        help="Project directory (default: current directory)",
    )
    stop_parser.add_argument(
        "--port", type=int, default=8420,
        help="Listen port (default: 8420)",
    )

    # vessal status
    status_parser = subparsers.add_parser("status", help="Query Agent status")
    status_parser.add_argument(
        "--port", type=int, default=8420,
        help="Listen port (default: 8420)",
    )

    # vessal skill
    skill_parser = subparsers.add_parser("skill", help="Skill management")
    skill_sub = skill_parser.add_subparsers(dest="skill_command")
    skill_sub.add_parser("create", help="Create Skill scaffold (wizard)")
    skill_check_parser = skill_sub.add_parser("check", help="Check Skill compliance")
    skill_check_parser.add_argument("path", type=str, help="Skill directory path")
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

    if args.command == "start":
        _cmd_start(args)
    elif args.command == "stop":
        _cmd_stop(args)
    elif args.command == "status":
        _cmd_status(args)
    elif args.command == "skill":
        if args.skill_command == "create":
            _cmd_skill_create(args)
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
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
