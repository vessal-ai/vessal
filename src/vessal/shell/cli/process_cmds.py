"""process_cmds.py — start / stop / status CLI command implementations."""
from __future__ import annotations

import argparse
import fcntl
import sys
from pathlib import Path

from vessal.ark.shell.cli.process_utils import (
    _is_project_running,
    _is_port_in_use,
    _read_lock_port,
    _read_lock_pid,
    _wait_for_health,
    _wait_for_lock_release,
)


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

    from vessal.ark.shell.server import ShellServer

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
