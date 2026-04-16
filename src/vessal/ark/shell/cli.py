"""cli.py — Vessal CLI entry point: start / stop / send / status / read / init / skill subcommands."""
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

    # vessal send
    send_parser = subparsers.add_parser("send", help="Send message to Agent inbox")
    send_parser.add_argument("message", type=str, help="Message content")
    send_parser.add_argument(
        "--port", type=int, default=8420,
        help="Shell port (default: 8420)",
    )

    # vessal status
    status_parser = subparsers.add_parser("status", help="Query Agent status")
    status_parser.add_argument(
        "--port", type=int, default=8420,
        help="Listen port (default: 8420)",
    )

    # vessal read
    read_parser = subparsers.add_parser("read", help="Read Agent replies")
    read_parser.add_argument(
        "--port", type=int, default=8420,
        help="Shell port (default: 8420)",
    )
    read_parser.add_argument(
        "--wait", type=float, default=0,
        help="Maximum seconds to wait for a reply (default: 0 = no wait)",
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

    args = parser.parse_args()

    if args.command == "start":
        _cmd_start(args)
    elif args.command == "stop":
        _cmd_stop(args)
    elif args.command == "send":
        _cmd_send(args)
    elif args.command == "status":
        _cmd_status(args)
    elif args.command == "read":
        _cmd_read(args)
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
        print(f"Agent started (PID {proc.pid})")
        print(f"  Log viewer: http://localhost:{args.port}/logs")
        print(f"  Stop: vessal stop")
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

    print(f"Shell server started: http://0.0.0.0:{args.port}")
    print(f"  Log viewer: http://localhost:{args.port}/logs")
    hull_cfg = config.get("hull", {})
    if "chat" in hull_cfg.get("skills", []):
        print(f"  Chat UI: http://127.0.0.1:{args.port}/skills/chat/")
    if "ui" in hull_cfg.get("skills", []):
        print(f"  Agent UI: http://127.0.0.1:{args.port}/skills/ui/")

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


def _cmd_send(args: argparse.Namespace) -> None:
    """Send a message to the Human Skill inbox."""
    import json
    import urllib.request
    import urllib.error

    # Chat Skill inbox endpoint (/skills/chat/ namespace)
    url = f"http://localhost:{args.port}/skills/chat/inbox"
    data = json.dumps({"content": args.message}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"Sent ({resp.status})")
    except urllib.error.URLError as e:
        print(f"Error: cannot connect to Agent ({e})", file=sys.stderr)
        sys.exit(1)


def _cmd_read(args: argparse.Namespace) -> None:
    """Read Agent replies (from Human Skill outbox)."""
    import json
    import time
    import urllib.request
    import urllib.error

    # Chat Skill outbox endpoint (/skills/chat/ namespace)
    url = f"http://localhost:{args.port}/skills/chat/outbox"
    deadline = time.time() + args.wait if args.wait > 0 else 0
    found = False

    while True:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read())
                for msg in data.get("messages", []):
                    print(msg.get("content", ""))
                    found = True
        except urllib.error.URLError as e:
            print(f"Error: cannot connect to Agent ({e})", file=sys.stderr)
            sys.exit(1)

        if found or deadline == 0 or time.time() >= deadline:
            break
        time.sleep(1)

    if not found and args.wait > 0:
        print("(no reply)")


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
    class_name = "".join(part.capitalize() for part in skill_name.split("_"))
    (base / "tests").mkdir(parents=True, exist_ok=True)

    (base / "__init__.py").write_text(
        f'"""{skill_name} — (one-line description)"""\n'
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
        f'    description = "(functional description, ≤15 words)"\n'
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
        f'description: "(functional description, ≤15 words)"\n'
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
