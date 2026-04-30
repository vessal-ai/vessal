"""errors.py — Shell-level exceptions for user-recoverable CLI conditions.

Any exception in this module represents a condition that the CLI understands
and can translate into a friendly one-line message + non-zero exit, without
printing a Python traceback. Boot-surface smoke tests enforce this contract.
"""
from __future__ import annotations


class CliUserError(Exception):
    """Raised when the user provided invalid input or the environment is in a
    state Vessal understands (e.g. target directory already exists). The CLI
    entry point catches this, prints the message, and exits with code 1.
    """
