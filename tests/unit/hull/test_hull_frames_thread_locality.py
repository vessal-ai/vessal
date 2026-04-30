from __future__ import annotations

import threading
from pathlib import Path

import pytest


@pytest.fixture
def hull(tmp_path: Path):
    from vessal.hull.hull import Hull
    from vessal.shell.cli.project_scaffold import write_project_scaffold

    project = tmp_path / "agent"
    write_project_scaffold(project, install_venv=False)
    (project / ".env").write_text(
        "OPENAI_API_KEY=sk-test\n"
        "OPENAI_BASE_URL=http://127.0.0.1:1\n"
        "OPENAI_MODEL=gpt-4o\n",
        encoding="utf-8",
    )
    return Hull(str(project))


def test_frames_callable_from_worker_thread(hull):
    result: list = []
    error: list = []

    def worker():
        try:
            result.append(hull.frames(after=None))
        except Exception as exc:
            error.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert error == [], f"Unexpected exception on worker thread: {error}"
    assert isinstance(result[0], list)


def test_frames_returns_list(hull):
    assert isinstance(hull.frames(after=None), list)
