"""test_memory — Memory Skill tests."""
import json
import pytest
from vessal.skills.memory.skill import Memory


def test_memory_is_skillbase():
    from vessal.skills._base import BaseSkill
    assert issubclass(Memory, BaseSkill)


def test_memory_has_required_attrs():
    assert isinstance(Memory.name, str) and Memory.name
    assert isinstance(Memory.description, str) and Memory.description


def test_save_and_get():
    m = Memory()
    m.save("key1", "value1")
    assert m.get("key1") == "value1"


def test_save_overwrite():
    m = Memory()
    m.save("key", "first")
    m.save("key", "second")
    assert m.get("key") == "second"


def test_delete():
    m = Memory()
    m.save("key1", "value1")
    m.delete("key1")
    assert m.get("key1") is None


def test_delete_nonexistent():
    m = Memory()
    m.delete("nope")  # should not raise


def test_get_nonexistent():
    m = Memory()
    assert m.get("nope") is None


def test_save_various_types():
    m = Memory()
    m.save("int", 42)
    m.save("list", [1, 2, 3])
    m.save("dict", {"a": 1})
    assert m.get("int") == 42
    assert m.get("list") == [1, 2, 3]


def test_signal_empty_when_no_memories():
    m = Memory()
    m.signal_update()
    assert m.signal == {}


def test_signal_shows_all_memories():
    m = Memory()
    m.save("a", 1)
    m.save("b", "hello")
    m.signal_update()
    assert m.signal != {}
    body = m.signal["entries"]
    assert "a" in body
    assert "b" in body


def test_no_persistence_without_ns():
    m = Memory()
    assert m._data_dir is None


def test_persistence_saves_on_save(tmp_path, monkeypatch):
    monkeypatch.setenv("VESSAL_DATA_DIR", str(tmp_path))
    m = Memory()
    m.save("key1", "value1")
    mem_file = tmp_path / "memory" / "memory.json"
    data = json.loads(mem_file.read_text())
    assert data["key1"] == "value1"


def test_persistence_loads_on_init(tmp_path, monkeypatch):
    monkeypatch.setenv("VESSAL_DATA_DIR", str(tmp_path))
    m1 = Memory()
    m1.save("key1", "value1")
    m2 = Memory()
    assert m2.get("key1") == "value1"


def test_persistence_corrupted_file(tmp_path, monkeypatch):
    data_dir = tmp_path / "memory"
    data_dir.mkdir(parents=True)
    mem_file = data_dir / "memory.json"
    mem_file.write_text("NOT JSON{{{", encoding="utf-8")
    monkeypatch.setenv("VESSAL_DATA_DIR", str(tmp_path))
    m = Memory()
    assert m._store == {}


class TestDrop:
    """memory.drop() is a no-op stub until PR-Compaction-Cell re-implements it for SQLite."""

    def test_drop_prints_not_available_warning(self, capsys):
        m = Memory()
        m._ns = {}
        m.drop(2)
        output = capsys.readouterr().out
        assert "not available" in output or "SQLite" in output


class TestContextPressureSignal:
    """Memory.signal_update() shows context pressure warning when threshold exceeded."""

    def test_no_warning_below_threshold(self):
        m = Memory()
        m._ns = {"_context_pct": 30}
        m.signal_update()
        # No memories and no warning → empty signal
        assert m.signal == {}

    def test_warning_at_threshold(self):
        m = Memory()
        m._ns = {"_context_pct": 50}
        m.signal_update()
        assert m.signal != {}
        body = m.signal["entries"]
        assert "50%" in body

    def test_warning_above_threshold(self):
        m = Memory()
        m._ns = {"_context_pct": 70}
        m.signal_update()
        assert m.signal != {}
        body = m.signal["entries"]
        assert "70%" in body

    def test_custom_threshold(self):
        m = Memory()
        m._ns = {"_context_pct": 40, "_compress_threshold": 30}
        m.signal_update()
        assert m.signal != {}  # 40 >= 30, should warn

    def test_memories_and_warning_combined(self):
        m = Memory()
        m._ns = {"_context_pct": 60}
        m.save("key1", "value1")
        m.signal_update()
        assert m.signal != {}
        body = m.signal["entries"]
        assert "key1" in body  # memories still shown
        assert "60%" in body   # warning also shown
