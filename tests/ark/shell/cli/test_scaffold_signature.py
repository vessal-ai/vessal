"""test_scaffold_signature — scaffold writes class __init__(self, ns=None)."""
from __future__ import annotations

from pathlib import Path

import pytest

from vessal.ark.shell.cli.scaffold import write_skill_scaffold


def test_scaffolded_skill_accepts_ns(tmp_path):
    base = tmp_path / "demo"
    base.mkdir()
    write_skill_scaffold(base, "demo")

    source = (base / "skill.py").read_text()
    assert "def __init__(self, ns=None):" in source, \
        f"scaffold must produce ns=None signature. Got:\n{source}"
    assert "self._ns = ns" in source, \
        "scaffold must store the ns argument on the instance"


def test_scaffold_accepts_new_kwargs(tmp_path):
    base = tmp_path / "demo"
    base.mkdir()
    write_skill_scaffold(
        base, "demo",
        with_tutorial=False, with_ui=False, with_server=False,
    )
    assert (base / "SKILL.md").exists()
    assert not (base / "TUTORIAL.md").exists()
    assert not (base / "ui" / "index.html").exists()
    assert not (base / "server.py").exists()


def test_scaffold_signature_no_longer_has_description(tmp_path):
    import inspect
    sig = inspect.signature(write_skill_scaffold)
    assert "description" not in sig.parameters
    assert {"with_tutorial", "with_ui", "with_server"} <= set(sig.parameters)


def test_skill_md_contains_spec_guidance_sections(tmp_path):
    base = tmp_path / "demo"
    base.mkdir()
    write_skill_scaffold(base, "demo")
    body = (base / "SKILL.md").read_text(encoding="utf-8")
    assert "## Methods" in body
    assert "## Protocol conventions" in body
    assert "## Common pitfalls" in body
    assert "(functional description, \u226415 words)" in body


def test_scaffold_emits_tutorial_when_flag_true(tmp_path):
    base = tmp_path / "demo"
    base.mkdir()
    write_skill_scaffold(base, "demo", with_tutorial=True)
    text = (base / "TUTORIAL.md").read_text(encoding="utf-8")
    assert "# demo \u2014 Development Guide" in text
    assert "SORA" in text                      # mental model section present
    assert "Checklist before publishing" in text


def test_scaffold_emits_ui_when_flag_true(tmp_path):
    base = tmp_path / "demo"
    base.mkdir()
    write_skill_scaffold(base, "demo", with_ui=True)
    html = (base / "ui" / "index.html").read_text(encoding="utf-8")
    assert "<button" in html
    assert "/skills/demo/hello" in html
    assert "fetch(" in html


def test_scaffold_emits_server_when_flag_true(tmp_path):
    base = tmp_path / "demo"
    base.mkdir()
    write_skill_scaffold(base, "demo", with_server=True)
    text = (base / "server.py").read_text(encoding="utf-8")
    assert "def hello" in text
    assert "routes" in text
