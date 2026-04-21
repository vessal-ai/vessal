"""test_scaffold_signature — scaffold writes class __init__(self, ns=None)."""
from __future__ import annotations

from pathlib import Path

import pytest

from vessal.ark.shell.cli.scaffold import write_skill_scaffold


def test_scaffolded_skill_accepts_ns(tmp_path):
    base = tmp_path / "demo"
    base.mkdir()
    write_skill_scaffold(base, "demo", "demo skill")

    source = (base / "skill.py").read_text()
    assert "def __init__(self, ns=None):" in source, \
        f"scaffold must produce ns=None signature. Got:\n{source}"
    assert "self._ns = ns" in source, \
        "scaffold must store the ns argument on the instance"
