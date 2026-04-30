"""upgrade — installer detection, PyPI latest-version lookup, upgrade command builder.

Detects whether `vessal` was installed via `uv tool`, `pipx`, or plain `pip`
by inspecting sys.executable's path, then builds the correct upgrade command
for the detected backend.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path


def check_pypi_latest(package: str) -> str:
    """Fetch the latest version of `package` from PyPI JSON API."""
    url = f"https://pypi.org/pypi/{package}/json"
    with urllib.request.urlopen(url, timeout=10) as resp:
        body = json.loads(resp.read())
    return body["info"]["version"]


def is_newer(candidate: str, *, current: str) -> bool:
    """Compare semver-ish strings lexicographically by tuple of ints.

    Non-numeric suffixes (e.g. 'rc1') are treated as 0 for simplicity.
    """
    def _parts(v: str) -> tuple[int, ...]:
        out: list[int] = []
        for chunk in v.split("."):
            digits = ""
            for ch in chunk:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            out.append(int(digits) if digits else 0)
        return tuple(out)

    return _parts(candidate) > _parts(current)


def detect_installer() -> str:
    """Detect how the running `vessal` CLI was installed.

    Returns one of "uv", "pipx", "pip", or "unknown".
    """
    exe = Path(sys.executable).resolve()
    parts = {p.lower() for p in exe.parts}
    path_str = str(exe).lower()

    if "uv" in parts and "tools" in parts:
        return "uv"
    if "/uv/tools/" in path_str or "\\uv\\tools\\" in path_str:
        return "uv"
    if "pipx" in parts:
        return "pipx"
    return "pip"


def build_upgrade_cmd(installer: str, package: str = "vessal") -> list[str]:
    """Return argv for the correct upgrade command."""
    if installer == "uv":
        return ["uv", "tool", "upgrade", package]
    if installer == "pipx":
        return ["pipx", "upgrade", package]
    return [sys.executable, "-m", "pip", "install", "--upgrade", package]
