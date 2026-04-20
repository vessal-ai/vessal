"""cli.py — Vessal CLI entry point: start / stop / status / init / skill subcommands."""
from __future__ import annotations

import argparse
import fcntl
import sys
from pathlib import Path

from vessal.ark.shell.server import ShellServer


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
    elif args.command == "init":
        _cmd_init(args)
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
        parser.print_help()
        sys.exit(1)


def _cmd_start(args: argparse.Namespace) -> None:
    """Start Agent server. Runs in foreground by default (--daemon for background)."""
    if not getattr(args, "daemon", False):
        _start_foreground(args)
        return

    import subprocess

    project_dir = Path(args.dir).resolve()
    if not (project_dir / "hull.toml").exists():
        print(f"Error: {project_dir} is not a Vessal project (hull.toml not found).", file=sys.stderr)
        sys.exit(1)

    data_dir = project_dir / "data"
    data_dir.mkdir(exist_ok=True)
    lock_path = data_dir / "vessal.lock"
    log_file = data_dir / "daemon.log"

    # Pre-check 1: is the project already running?
    if _is_project_running(lock_path):
        port = _read_lock_port(lock_path)
        print(f"Error: project is already running (port {port})", file=sys.stderr)
        sys.exit(1)

    # Pre-check 2: is the port already in use?
    if _is_port_in_use(args.port):
        print(f"Error: port {args.port} is already in use", file=sys.stderr)
        sys.exit(1)

    # Launch subprocess (foreground mode by default; subprocess acquires flock itself)
    cmd = [
        sys.executable, "-m", "vessal", "start",
        "--dir", str(project_dir),
        "--port", str(args.port),
    ]
    with open(log_file, "a") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=log, start_new_session=True)

    # Verify startup (health check)
    if _wait_for_health(args.port, timeout=5):
        print(f"Vessal agent running (PID {proc.pid}).")
        print(f"  Console: http://127.0.0.1:{args.port}/console/")
        print(f"  Stop:    vessal stop")
    else:
        lines = []
        if log_file.exists():
            lines = log_file.read_text().strip().splitlines()[-10:]
        print("Error: Agent failed to start", file=sys.stderr)
        for line in lines:
            print(f"  {line}", file=sys.stderr)
        sys.exit(1)


def _start_foreground(args: argparse.Namespace) -> None:
    """Run Agent server in the foreground.

    Shell (HTTP gateway + supervisor) runs in the main process.
    Hull (Agent core) runs in a subprocess.

    Args:
        args: Command-line arguments containing dir and port fields.
    """
    import os
    import subprocess
    import tomllib

    project_dir = Path(args.dir).resolve()
    if not (project_dir / "hull.toml").exists():
        print(
            f"Error: {project_dir} is not a Vessal project (hull.toml not found).",
            file=sys.stderr,
        )
        sys.exit(1)

    # flock mutual exclusion (held by Shell main process)
    data_dir = project_dir / "data"
    data_dir.mkdir(exist_ok=True)
    lock_path = data_dir / "vessal.lock"
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        existing_port = _read_lock_port(lock_path)
        print(f"Error: project is already running (port {existing_port})", file=sys.stderr)
        lock_fd.close()
        sys.exit(1)
    lock_fd.write(f"{args.port}\n{os.getpid()}\n")
    lock_fd.flush()

    # Read hull.toml (used only for printing info and companion)
    with open(project_dir / "hull.toml", "rb") as f:
        config = tomllib.load(f)

    # Create ShellServer (manages Hull subprocess)
    shell = ShellServer(project_dir=str(project_dir), port=args.port)

    companion_procs: list[tuple[str, subprocess.Popen]] = []

    try:
        shell.start()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        lock_fd.close()
        lock_path.unlink(missing_ok=True)
        sys.exit(1)

    print(f"Vessal agent running.")
    print(f"  Console: http://127.0.0.1:{args.port}/console/")
    print(f"  Stop:    vessal stop")

    # Start companion processes (consistent with existing logic)
    import shlex

    companions = config.get("companion", {})
    for comp_name, comp_cfg in companions.items():
        cmd = comp_cfg.get("command", "")
        cwd_rel = comp_cfg.get("cwd", ".")
        if not cmd:
            continue
        full_cwd = str(project_dir / cwd_rel)
        args_list = shlex.split(cmd)
        if args_list and args_list[0] in ("python", "python3"):
            args_list[0] = sys.executable
        port = comp_cfg.get("port")
        if port is not None and "--port" not in args_list:
            args_list.extend(["--port", str(port)])
        proc = subprocess.Popen(args_list, cwd=full_cwd)
        companion_procs.append((comp_name, proc))

    try:
        shell.serve_forever()
    except KeyboardInterrupt:
        print("\nGoodbye.")
    finally:
        shell.shutdown()
        for comp_name, proc in companion_procs:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        lock_fd.close()
        lock_path.unlink(missing_ok=True)


def _cmd_stop(args: argparse.Namespace) -> None:
    """Stop a running Agent. Sends HTTP /stop and waits for process to exit (flock released).

    Args:
        args: CLI arguments containing dir and port.
    """
    import os
    import signal
    import urllib.request
    import urllib.error

    project_dir = Path(getattr(args, "dir", ".")).resolve()
    lock_path = project_dir / "data" / "vessal.lock"

    # Check if running
    if not _is_project_running(lock_path):
        print("Agent is not running")
        return

    port = _read_lock_port(lock_path)
    if port is None:
        print("Error: lock file format is invalid", file=sys.stderr)
        sys.exit(1)

    # Send stop signal
    url = f"http://localhost:{port}/stop"
    req = urllib.request.Request(url, data=b"", method="POST")
    try:
        urllib.request.urlopen(req, timeout=5)
    except urllib.error.URLError:
        # HTTP unreachable, force SIGKILL
        pid = _read_lock_pid(lock_path)
        if pid:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            print(f"Agent force-stopped (PID {pid})")
            return
        print("Error: unable to stop Agent", file=sys.stderr)
        sys.exit(1)

    # Wait for process to exit (flock released)
    if _wait_for_lock_release(lock_path, timeout=30):
        print("Agent stopped")
    else:
        pid = _read_lock_pid(lock_path)
        if pid:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            print(f"Agent force-stopped (PID {pid})")
        else:
            print("Error: stop timed out", file=sys.stderr)
            sys.exit(1)


def _cmd_status(args: argparse.Namespace) -> None:
    """Query Agent status.

    Queries current Agent state via GET /status endpoint.
    """
    import json
    import urllib.request
    import urllib.error

    url = f"http://localhost:{args.port}/status"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            print(f"Status: {'idle' if data.get('idle') else 'active'}")
            print(f"Frame: {data.get('frame', 0)}")
            if data.get('wake'):
                print(f"Wake: {data.get('wake')}")
    except urllib.error.URLError as e:
        print(f"Error: cannot connect to Agent ({e})", file=sys.stderr)
        sys.exit(1)


def _cmd_init(args: argparse.Namespace) -> None:
    """Execute vessal init command.

    Creates project directory, generates hull.toml, SOUL.md, pyproject.toml, .env.example,
    .gitignore, skills/example/ example Skill package, and sets up the virtual environment.
    Detects uv (runs uv sync) or falls back to python -m venv + pip install vessal.
    Pass --no-venv to skip virtual environment creation.
    Exits with error if directory already exists.
    """
    project_dir = Path(args.name)
    if project_dir.exists():
        print(f"Error: directory {args.name} already exists.", file=sys.stderr)
        sys.exit(1)

    project_dir.mkdir(parents=True)

    # Three-directory skill layout: bundled (preinstalled), hub (SkillHub downloads), local (user-developed)
    import shutil
    bundled_dir = project_dir / "skills" / "bundled"
    hub_dir = project_dir / "skills" / "hub"
    local_dir = project_dir / "skills" / "local"

    builtin_skills_src = Path(__file__).resolve().parent.parent.parent / "skills"
    if builtin_skills_src.exists():
        shutil.copytree(str(builtin_skills_src), str(bundled_dir),
                        ignore=shutil.ignore_patterns("__pycache__"))
    else:
        bundled_dir.mkdir(parents=True)

    hub_dir.mkdir(parents=True, exist_ok=True)
    local_dir.mkdir(parents=True, exist_ok=True)

    # hull.toml
    (project_dir / "hull.toml").write_text(
        f"""[agent]
name = "{args.name}"
language = "en"

[cell]
max_frames = 100
# Context budget (token count), should match the model's actual window size
# context_budget = 128000

[core]
timeout = 60
max_retries = 3

[core.api_params]
# Passed through to chat.completions.create(); supports any model parameters
temperature = 0.7
max_tokens = 4096
# Model-specific parameters as needed:
# top_p = 0.9
# top_k = 40

[hull]
skills = ["tasks", "pin", "chat", "heartbeat"]
skill_paths = ["skills/bundled", "skills/hub", "skills/local"]
# compress_threshold = 50  # Context pressure signal threshold (default 50%, read by Memory skill)

[gates]
# Gate conditions (see docs)
""",
        encoding="utf-8",
    )

    # SOUL.md — Agent identity definition
    # Loaded automatically by Hull at startup into _system_prompt variable,
    # presented to the LLM as a system prompt section.
    # The Agent can modify SOUL.md during runtime to accumulate experience;
    # writing it back persists across episodes.
    (project_dir / "SOUL.md").write_text(
        f"""\
# {args.name} Agent Identity

## Role
You are a general-purpose assistant.

## Behavioral Preferences
- Prefer Python standard library; avoid unnecessary dependencies
- Verify paths exist before operating on files
- When encountering errors, read the frame stream to diagnose the cause before deciding next steps

## Accumulated Experience
(The Agent may append experience here during runtime; writing back persists across episodes)
""",
        encoding="utf-8",
    )

    # pyproject.toml
    (project_dir / "pyproject.toml").write_text(
        f"""[project]
name = "{args.name}"
version = "0.1.0"
description = "Vessal Agent"
requires-python = ">=3.12"
dependencies = ["vessal"]
""",
        encoding="utf-8",
    )

    # .env.example
    (project_dir / ".env.example").write_text(
        "OPENAI_API_KEY=your-api-key-here\n"
        "OPENAI_BASE_URL=https://api.openai.com/v1\n"
        "OPENAI_MODEL=gpt-4o\n",
        encoding="utf-8",
    )

    # .gitignore
    (project_dir / ".gitignore").write_text(
        """.env
.venv/
snapshots/
logs/
__pycache__/
""",
        encoding="utf-8",
    )

    # skills/local/example/ — example Skill package
    # Demonstrates Skill development conventions: module docstrings, __all__, function docstrings, type annotations
    example_dir = local_dir / "example"
    example_dir.mkdir()

    (example_dir / "__init__.py").write_text(
        '''\
"""Example toolkit

Provides basic text processing and math utilities, demonstrating Skill package conventions.
"""

__all__ = ["word_count", "reverse_text", "add", "multiply"]


def word_count(text: str) -> int:
    """Count the number of words in text.

    text: input string to count words in
    returns: number of words (split by whitespace)
    """
    return len(text.split())


def reverse_text(text: str) -> str:
    """Reverse a string.

    text: string to reverse
    returns: reversed string
    """
    return text[::-1]


def add(a: float, b: float) -> float:
    """Return the sum of two numbers.

    a: first number
    b: second number
    returns: a + b
    """
    return a + b


def multiply(a: float, b: float) -> float:
    """Return the product of two numbers.

    a: first number
    b: second number
    returns: a * b
    """
    return a * b
''',
        encoding="utf-8",
    )

    # skills/example/SKILL.md — usage guide example
    (example_dir / "SKILL.md").write_text(
        """\
---
name: example
version: "1.0"
description: "Example toolkit"
tags: [example, demo]
category: development
---

# example

Example toolkit. Provides basic text processing and math utilities, demonstrating Skill package conventions.
Load and call via example.word_count() etc.

## API

    example.word_count(text: str) -> int
    example.reverse_text(text: str) -> str
    example.add(a, b) -> number
    example.multiply(a, b) -> number
""",
        encoding="utf-8",
    )

    # requirements.txt (example: empty file, showing where to declare dependencies)
    (example_dir / "requirements.txt").write_text(
        "# Declare Python package dependencies for this Skill, one per line\n# e.g.: requests>=2.28\n",
        encoding="utf-8",
    )

    # gates/ — custom gate rule files
    gates_dir = project_dir / "gates"
    gates_dir.mkdir(exist_ok=True)

    (gates_dir / "action_gate.py").write_text(
        '"""action_gate.py — Custom action safety rules.\n'
        '\n'
        'Define check(code: str) -> tuple[bool, str] function.\n'
        'Return (True, "") to allow execution, (False, "reason") to deny.\n'
        'This file is optional — delete it to use default patterns from hull.toml [gates].\n'
        '"""\n'
        '\n'
        '\n'
        'def check(code: str) -> tuple[bool, str]:\n'
        '    # Example: forbid deletion of root directory\n'
        '    # if "shutil.rmtree" in code and ("/" == code or "~" in code):\n'
        '    #     return False, "deleting system directories is forbidden"\n'
        '    return True, ""\n',
        encoding="utf-8",
    )

    (gates_dir / "state_gate.py").write_text(
        '"""state_gate.py — Custom state validation rules.\n'
        '\n'
        'Define check(state: str) -> tuple[bool, str] function.\n'
        'Return (True, "") to allow sending, (False, "reason") to deny.\n'
        'This file is optional — delete it to use default patterns from hull.toml [gates].\n'
        '"""\n'
        '\n'
        '\n'
        'def check(state: str) -> tuple[bool, str]:\n'
        '    # Example: limit context length\n'
        '    # if len(state) > 500_000:\n'
        '    #     return False, "context is too long"\n'
        '    return True, ""\n',
        encoding="utf-8",
    )

    # Create virtual environment and install dependencies
    import subprocess as sp
    if not getattr(args, "no_venv", False):
        if shutil.which("uv"):
            sp.run(["uv", "sync"], cwd=str(project_dir), check=True)
        else:
            venv_dir = project_dir / ".venv"
            sp.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            bin_dir = "Scripts" if sys.platform == "win32" else "bin"
            venv_python = str(venv_dir / bin_dir / "python")
            sp.run([venv_python, "-m", "pip", "install", "vessal"], check=True)

    print(f"\nDone! Project '{args.name}' is ready.\n")
    print(f"  cd {args.name}")
    print(f"  cp .env.example .env")
    print(f"  # Fill in OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL")
    print()
    print(f"  vessal start")


_DEFAULT_DESCRIPTION = "(functional description, ≤15 words)"


def write_skill_scaffold(base: Path, skill_name: str, description: str = _DEFAULT_DESCRIPTION) -> None:
    """Write a Skill scaffold into `base` with Python identifier `skill_name`.

    Creates: __init__.py, skill.py, SKILL.md, requirements.txt, tests/__init__.py,
    tests/test_{skill_name}.py. Shared between the `vessal skill init` CLI and the
    `skill_creator` Skill.
    """
    class_name = "".join(part.capitalize() for part in skill_name.split("_"))
    (base / "tests").mkdir(parents=True, exist_ok=True)

    (base / "__init__.py").write_text(
        f'"""{skill_name} — {description}"""\n'
        f'from .skill import {class_name} as Skill\n\n'
        f'__all__ = ["Skill"]\n',
        encoding="utf-8",
    )
    (base / "skill.py").write_text(
        f'"""skill.py — {skill_name} Skill implementation."""\n'
        f'from __future__ import annotations\n'
        f'\n'
        f'from vessal.ark.shell.hull.skill import SkillBase\n'
        f'\n'
        f'\n'
        f'class {class_name}(SkillBase):\n'
        f'    name = "{skill_name}"\n'
        f'    description = "{description}"\n'
        f'\n'
        f'    # ── Protocol conventions ──\n'
        f'    # 1. description ≤15 words, describe function not method names\n'
        f'    # 2. _signal() only shows state, does not expose method signatures\n'
        f'    # 3. SKILL.md is the only place containing method signatures\n'
        f'    # 4. _prompt() only contains behavior rules, not the API\n'
        f'\n'
        f'    def __init__(self):\n'
        f'        super().__init__()\n'
        f'        # Protect internal state with _ prefix to prevent Agent from bypassing the API\n'
        f'        # self._cache = {{}}\n'
        f'\n'
        f'    # Public methods: callable by Agent. Must produce observable feedback (print/return value/namespace diff)\n'
        f'    # def my_function(self, arg: str) -> str:\n'
        f'    #     """Tool description."""\n'
        f'    #     return arg\n'
        f'\n'
        f'    # Signal (optional, called each frame, returns (title, body) tuple)\n'
        f'    # def _signal(self) -> tuple[str, str] | None:\n'
        f'    #     return ("{skill_name}", "status info, no method names")\n',
        encoding="utf-8",
    )
    (base / "SKILL.md").write_text(
        # frontmatter for skills.list() discovery; body is the guide attribute (Agent reads via print(name.guide))
        f'---\n'
        f'name: {skill_name}\n'
        f'version: "0.1.0"\n'
        f'description: "{description}"\n'
        f'author: ""\n'
        f'license: "Apache-2.0"\n'
        f'requires:\n'
        f'  skills: []\n'
        f'---\n'
        f'\n'
        f'# {skill_name}\n'
        f'\n'
        f'(Operation manual. Agent reads via print({skill_name}.guide).\n'
        f'Contains method signatures and usage examples; keep concise.)\n'
        f'\n'
        f'## Methods\n'
        f'\n'
        f'(List method signatures.)\n',
        encoding="utf-8",
    )
    (base / "requirements.txt").write_text("", encoding="utf-8")
    (base / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (base / "tests" / f"test_{skill_name}.py").write_text(
        f'"""test_{skill_name} — {skill_name} Skill basic tests"""\n\n\n'
        f'def test_{skill_name}_placeholder():\n'
        f'    """Placeholder test; replace with real tests."""\n'
        f'    pass\n',
        encoding="utf-8",
    )


def _cmd_skill_init(args: argparse.Namespace) -> None:
    """Create a Skill scaffold directory.

    Args:
        args: argparse result; args.name is the Skill name.
    Side effects:
        Creates <name>/ scaffold directory in the current directory.
    """
    name = args.name
    base = Path(name)
    skill_name = base.name  # leaf directory name, used as Python identifier and Skill name
    write_skill_scaffold(base, skill_name)
    print(f"Skill '{skill_name}' scaffold created at ./{name}/")


def _cmd_skill_check(args: argparse.Namespace) -> None:
    """Check Skill directory compliance.

    Checks __init__.py, skill.py, SKILL.md, and SkillBase inheritance.
    With --test, additionally runs tests/ directory.
    Exits with code 1 if any FAIL; exits with code 0 if only WARNs.
    """
    import importlib
    import subprocess

    from vessal.ark.shell.hull.skill_manager import _parse_skill_md as parse_skill_md

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

    # 5. Module import + SkillBase check
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
                from vessal.ark.shell.hull.skill import SkillBase
                if issubclass(skill_cls, SkillBase):
                    ok(f"Skill inherits SkillBase: {skill_cls.__name__}")
                else:
                    fail(f"Skill {skill_cls.__name__!r} does not inherit SkillBase")

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
    from vessal.ark.shell.hull.skill_manager import _parse_skill_md

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
    from vessal.ark.shell.hull.skill_manager import _parse_skill_md

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

    from vessal.ark.shell.hull.skill_manager import _parse_skill_md

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


# ── flock process lock helpers ──────────────────────────


def _is_project_running(lock_path: Path) -> bool:
    """Check whether the project is running (via flock probe).

    Args:
        lock_path: Lock file path (data/vessal.lock).

    Returns:
        True if the file is flock-locked (project is running).
    """
    if not lock_path.exists():
        return False
    try:
        fd = open(lock_path, "r+")
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            return False
        except BlockingIOError:
            return True
        finally:
            fd.close()
    except OSError:
        return False


def _read_lock_port(lock_path: Path) -> int | None:
    """Read port number from lock file (first line).

    Args:
        lock_path: Lock file path.

    Returns:
        Port number as int, or None on failure.
    """
    try:
        lines = lock_path.read_text().strip().splitlines()
        return int(lines[0]) if lines else None
    except (OSError, ValueError, IndexError):
        return None


def _read_lock_pid(lock_path: Path) -> int | None:
    """Read PID from lock file (second line).

    Args:
        lock_path: Lock file path.

    Returns:
        PID as int, or None on failure.
    """
    try:
        lines = lock_path.read_text().strip().splitlines()
        return int(lines[1]) if len(lines) > 1 else None
    except (OSError, ValueError, IndexError):
        return None


def _is_port_in_use(port: int) -> bool:
    """Check whether a port is in use (by attempting to connect to localhost).

    Args:
        port: Port number to check.

    Returns:
        True if the port is already in use.
    """
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("localhost", port)) == 0


def _wait_for_health(port: int, timeout: float = 5.0) -> bool:
    """Poll the health check endpoint, waiting for service readiness.

    Args:
        port: Port number to check.
        timeout: Maximum wait time in seconds.

    Returns:
        True if the service responded.
    """
    import time
    import urllib.request
    import urllib.error
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(f"http://localhost:{port}/status")
            urllib.request.urlopen(req, timeout=1)
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.3)
    return False


def _wait_for_lock_release(lock_path: Path, timeout: float = 30.0) -> bool:
    """Poll the lock file, waiting for the process to exit (lock released).

    Args:
        lock_path: Lock file path.
        timeout: Maximum wait time in seconds.

    Returns:
        True if the lock was released (process has exited).
    """
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _is_project_running(lock_path):
            return True
        time.sleep(0.5)
    return False
