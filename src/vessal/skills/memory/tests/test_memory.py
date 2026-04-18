"""test_memory — Memory Skill tests."""
import json
import pytest
from vessal.skills.memory.skill import Memory


def test_memory_is_skillbase():
    from vessal.ark.shell.hull.skill import SkillBase
    assert issubclass(Memory, SkillBase)


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
    result = m._signal()
    assert result is None


def test_signal_shows_all_memories():
    m = Memory()
    m.save("a", 1)
    m.save("b", "hello")
    result = m._signal()
    assert result is not None
    title, body = result
    assert "a" in body
    assert "b" in body


def test_no_persistence_without_ns():
    m = Memory()
    assert m._data_dir is None


def test_persistence_saves_on_save(tmp_path):
    ns = {"_data_dir": str(tmp_path)}
    m = Memory(ns=ns)
    m.save("key1", "value1")
    mem_file = tmp_path / "memory" / "memory.json"
    data = json.loads(mem_file.read_text())
    assert data["key1"] == "value1"


def test_persistence_loads_on_init(tmp_path):
    ns = {"_data_dir": str(tmp_path)}
    m1 = Memory(ns=ns)
    m1.save("key1", "value1")
    m2 = Memory(ns=ns)
    assert m2.get("key1") == "value1"


def test_persistence_corrupted_file(tmp_path):
    data_dir = tmp_path / "memory"
    data_dir.mkdir(parents=True)
    mem_file = data_dir / "memory.json"
    mem_file.write_text("NOT JSON{{{", encoding="utf-8")
    ns = {"_data_dir": str(tmp_path)}
    m = Memory(ns=ns)
    assert m._store == {}


class TestDrop:
    """memory.drop(n) physically deletes the oldest n frames from the hot zone."""

    def _make_ns_with_frames(self, n_frames: int, tmp_path=None) -> dict:
        from vessal.ark.shell.hull.cell.kernel.frame_stream import FrameStream
        fs = FrameStream(k=16, n=8)
        for i in range(n_frames):
            fs.commit_frame({
                "schema_version": 7,
                "number": i,
                "ping": {"system_prompt": "", "state": {"frame_stream": "", "signals": ""}},
                "pong": {"think": "", "action": {"operation": "", "expect": ""}},
                "observation": {"stdout": "", "diff": "", "error": None, "verdict": None},
            })
        ns = {"_frame_stream": fs}
        if tmp_path:
            ns["_data_dir"] = str(tmp_path)
        return ns

    def test_drop_removes_oldest_frames(self):
        ns = self._make_ns_with_frames(5)
        m = Memory(ns=ns)
        m.drop(2)
        assert ns["_frame_stream"].hot_frame_count() == 3

    def test_drop_zero_is_noop(self):
        ns = self._make_ns_with_frames(3)
        m = Memory(ns=ns)
        m.drop(0)
        assert ns["_frame_stream"].hot_frame_count() == 3

    def test_drop_more_than_available_keeps_one(self):
        ns = self._make_ns_with_frames(3)
        m = Memory(ns=ns)
        m.drop(100)
        assert ns["_frame_stream"].hot_frame_count() >= 1

    def test_drop_without_ns_raises(self):
        m = Memory()
        with pytest.raises(RuntimeError):
            m.drop(1)

    def test_drop_prints_pre_deletion_prompt(self, capsys):
        ns = self._make_ns_with_frames(5)
        m = Memory(ns=ns)
        m.drop(2)
        output = capsys.readouterr().out
        assert "Have you saved key information to memory" in output
        assert "Deleted" in output


class TestContextPressureSignal:
    """Memory._signal() shows context pressure warning when threshold exceeded."""

    def test_no_warning_below_threshold(self):
        ns = {"_context_pct": 30}
        m = Memory(ns=ns)
        result = m._signal()
        # No memories and no warning → None
        assert result is None

    def test_warning_at_threshold(self):
        ns = {"_context_pct": 50}
        m = Memory(ns=ns)
        result = m._signal()
        assert result is not None
        title, body = result
        assert "50%" in body

    def test_warning_above_threshold(self):
        ns = {"_context_pct": 70}
        m = Memory(ns=ns)
        result = m._signal()
        assert result is not None
        _, body = result
        assert "70%" in body

    def test_custom_threshold(self):
        ns = {"_context_pct": 40, "_compress_threshold": 30}
        m = Memory(ns=ns)
        result = m._signal()
        assert result is not None  # 40 >= 30, should warn

    def test_memories_and_warning_combined(self):
        ns = {"_context_pct": 60}
        m = Memory(ns=ns)
        m.save("key1", "value1")
        result = m._signal()
        assert result is not None
        _, body = result
        assert "key1" in body  # memories still shown
        assert "60%" in body   # warning also shown
