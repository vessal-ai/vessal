"""skill.py — pip Skill implementation."""
from __future__ import annotations

import re
import subprocess
import sys

from vessal.skills._base import BaseSkill

# Valid package name: alphanumeric, hyphens, underscores, dots, brackets (version constraints)
_VALID_PKG = re.compile(r"^[A-Za-z0-9._\-\[\]>=<!, ]+$")


class Pip(BaseSkill):
    """Python package installer.

    Attributes:
        name: "pip"
        description: "install Python packages"
    """

    name = "pip"
    description = "install pkg"

    def install(self, package: str) -> str:
        """Install a Python package into the current Python environment.

        Args:
            package: Package name (e.g. "requests", "numpy>=1.20").

        Returns:
            Installation result string.
        """
        package = package.strip()
        if not package or not _VALID_PKG.match(package):
            return f"Rejected: invalid package name {package!r}"

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return f"Timed out: {package}"
        except Exception as e:
            return f"Failed: {e}"

        if result.returncode == 0:
            return f"Installed: {package}"
        return f"Failed: {result.stderr.strip()}"
