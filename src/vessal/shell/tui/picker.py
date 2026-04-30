"""picker.py — root TUI menu shown when the user runs `vessal` or `vs` with no args."""
from __future__ import annotations

from pathlib import Path


def build_menu(cwd: Path, recent: list[str]) -> list[tuple[str, str]]:
    """Return a list of (label, action_key) for the picker.

    Action keys are consumed by run(); tests use labels only.
    """
    if (cwd / "hull.toml").exists():
        return [
            ("Run dev",        "dev"),
            ("Build image",    "build"),
            ("Install skill",  "skill_install"),
            ("Open Console",   "open_console"),
            ("Stop",           "stop"),
        ]
    items: list[tuple[str, str]] = [("Create new project", "create")]
    if recent:
        items.append(("Open recent…", "recent"))
    return items


def run(cwd: Path | None = None) -> int:
    """Run the TUI picker. Returns an exit code suitable for sys.exit."""
    from prompt_toolkit.shortcuts import radiolist_dialog

    from vessal.ark.shell.tui.recent import RecentProjects

    cwd = (cwd or Path.cwd()).resolve()
    recent = RecentProjects().list()
    items = build_menu(cwd, recent)
    if not items:
        print("No actions available.")
        return 1

    choice = radiolist_dialog(
        title="Vessal",
        text=str(cwd),
        values=items,
    ).run()
    if choice is None:
        return 0
    return _dispatch(choice, cwd, recent)


def _dispatch(action: str, cwd: Path, recent: list[str]) -> int:
    import os
    import subprocess
    import sys

    if action == "dev":
        return subprocess.call([sys.executable, "-m", "vessal.cli", "start", "--dir", str(cwd), "--foreground"])
    if action == "build":
        return subprocess.call([sys.executable, "-m", "vessal.cli", "build", str(cwd)])
    if action == "skill_install":
        name = input("Skill name or URL: ").strip()
        if not name:
            return 1
        return subprocess.call([sys.executable, "-m", "vessal.cli", "skill", "install", name])
    if action == "stop":
        return subprocess.call([sys.executable, "-m", "vessal.cli", "stop", "--dir", str(cwd)])
    if action == "open_console":
        import webbrowser
        url = _resolve_console_url(cwd)
        webbrowser.open(url)
        return 0
    if action == "create":
        from vessal.ark.shell.tui.create_wizard import run as wizard_run
        return wizard_run(cwd)
    if action == "recent":
        from prompt_toolkit.shortcuts import radiolist_dialog as _r
        choice = _r(title="Open recent", text="Select a project", values=[(p, p) for p in recent]).run()
        if choice is None:
            return 0
        os.chdir(choice)
        return run(Path(choice))
    return 1


def _resolve_console_url(cwd: Path) -> str:
    """Read data/runtime.json (written by ShellServer.start on bind) to find
    the actual port. Fall back to 8420 if the file is missing."""
    import json as _json
    runtime_file = cwd / "data" / "runtime.json"
    if runtime_file.exists():
        try:
            port = _json.loads(runtime_file.read_text(encoding="utf-8")).get("port", 8420)
            return f"http://127.0.0.1:{port}/console/"
        except (ValueError, OSError):
            pass
    return "http://127.0.0.1:8420/console/"
