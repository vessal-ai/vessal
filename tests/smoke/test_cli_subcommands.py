"""test_cli_subcommands.py — R14 smoke test for the boot surface.

Shipped with the cli/ subpackage split (P5 of 2026-04-20 layering refactor).
"""
from __future__ import annotations

import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "vessal.ark.shell.cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_top_level_help() -> None:
    r = _run("--help")
    assert r.returncode == 0, r.stderr
    assert "start" in r.stdout and "skill" in r.stdout


def test_start_help() -> None:
    r = _run("start", "--help")
    assert r.returncode == 0, r.stderr
    assert "--dir" in r.stdout and "--port" in r.stdout and "--daemon" in r.stdout


def test_stop_help() -> None:
    r = _run("stop", "--help")
    assert r.returncode == 0, r.stderr


def test_status_help() -> None:
    r = _run("status", "--help")
    assert r.returncode == 0, r.stderr


def test_vessal_create_has_no_positional_arg() -> None:
    """`vessal create foo` must fail — name is wizard-only (C7)."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "vessal.cli", "create", "foo"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0, "create should reject positional arg"


def test_vessal_init_removed() -> None:
    """`vessal init` must no longer be a recognized subcommand."""
    r = _run("init", "demo-proj")
    assert r.returncode != 0


def test_skill_list_help() -> None:
    r = _run("skill", "list", "--help")
    assert r.returncode == 0, r.stderr


def test_skill_create_help() -> None:
    r = _run("skill", "create", "--help")
    assert r.returncode == 0, r.stderr


def test_skill_install_help() -> None:
    r = _run("skill", "install", "--help")
    assert r.returncode == 0, r.stderr
