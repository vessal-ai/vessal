import json
from pathlib import Path
from vessal.ark.shell.hull.skills_manifest import write_manifest, read_manifest


def test_manifest_roundtrip(tmp_path: Path):
    loaded = {
        "chat": {"parent_path": "/skills", "is_package_skill": False},
        "memory": {"parent_path": "", "is_package_skill": True},
    }
    path = tmp_path / "snap.skills.json"
    write_manifest(path, loaded)
    assert json.loads(path.read_text())["chat"]["parent_path"] == "/skills"
    restored = read_manifest(path)
    assert restored == loaded


def test_manifest_read_missing_returns_empty(tmp_path: Path):
    assert read_manifest(tmp_path / "nope.skills.json") == {}
