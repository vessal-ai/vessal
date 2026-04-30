"""process_utils.py — flock process lock helpers for the Vessal CLI."""
from __future__ import annotations

import fcntl
from pathlib import Path


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
