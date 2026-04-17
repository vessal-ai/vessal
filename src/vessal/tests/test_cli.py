"""Smoke tests for vessal CLI surface."""
import subprocess
import sys


def test_send_subcommand_is_removed():
    result = subprocess.run(
        [sys.executable, "-m", "vessal.cli", "send", "hi"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "invalid choice: 'send'" in result.stderr or "unrecognized" in result.stderr


def test_read_subcommand_is_removed():
    result = subprocess.run(
        [sys.executable, "-m", "vessal.cli", "read"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "invalid choice: 'read'" in result.stderr or "unrecognized" in result.stderr


def test_help_still_works():
    result = subprocess.run(
        [sys.executable, "-m", "vessal.cli", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "start" in result.stdout
    assert "send" not in result.stdout
    assert "read" not in result.stdout
