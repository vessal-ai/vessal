"""rules.py — Built-in safety rule set.

Each rule is a function:
    check(action: str) -> str | None

Return None to pass through; return a string to indicate the block reason.

Built-in rules only block operations that are almost certainly not legitimate
Agent behavior:
- Recursive deletion of entire directory trees (root or home directory)
- Writes to critical system paths
- Bulk process killing

Not blocked:
- Ordinary file read/write (needed for normal Agent work)
- Network requests (needed by web_search and other skills)
- Importing third-party libraries (needed for normal development)
"""

from __future__ import annotations

import re


def _check_dangerous_rm(action: str) -> str | None:
    """Block shutil.rmtree calls targeting root or home directories."""
    patterns = [
        r'shutil\.rmtree\s*\(\s*["\']/',
        r'shutil\.rmtree\s*\(\s*["\']~',
        r'os\.system\s*\(\s*["\']rm\s+-rf\s+/',
    ]
    for pattern in patterns:
        if re.search(pattern, action):
            return f"Detected dangerous recursive delete: {pattern}"
    return None


def _check_system_path_write(action: str) -> str | None:
    """Block writes to system paths like /etc, /usr, /bin, etc."""
    system_paths = ["/etc/", "/usr/", "/bin/", "/sbin/", "/boot/", "/System/"]
    for path in system_paths:
        if f'open("{path}' in action or f"open('{path}" in action:
            if '"w"' in action or "'w'" in action or '"a"' in action or "'a'" in action:
                return f"Detected write to system path: {path}"
    return None


def _check_process_kill(action: str) -> str | None:
    """Block bulk process killing."""
    if re.search(r'os\.kill\s*\(\s*\d+\s*,\s*signal\.SIGKILL', action):
        return "Detected process kill with SIGKILL"
    if re.search(r'os\.system\s*\(\s*["\']kill\s+-9\s', action):
        return "Detected kill -9 via os.system"
    return None


# Rule registry — list of tuples; order determines execution order
BUILTIN_RULES: list[tuple[str, object]] = [
    ("dangerous_rm", _check_dangerous_rm),
    ("system_path_write", _check_system_path_write),
    ("process_kill", _check_process_kill),
]
