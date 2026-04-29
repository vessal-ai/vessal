"""test_tasks — Tasks Skill redesign tests."""
import pytest
from vessal.skills.tasks.skill import Tasks


def make_tasks():
    return Tasks()


def make_tasks_with_ns():
    """Create Tasks with a namespace dict for testing ns interactions."""
    ns = {}
    t = Tasks()
    t._ns = ns
    return t, ns


class TestAdd:
    def test_add_root_task(self):
        t = make_tasks()
        t.add("do something")
        assert "1" in t._tree
        assert t._tree["1"]["goal"] == "do something"
        assert t._tree["1"]["status"] == "active"
        assert t._tree["1"]["parent_id"] is None

    def test_add_second_root(self):
        t = make_tasks()
        t.add("first")
        t.add("second")
        assert "2" in t._tree
        assert t._tree["2"]["goal"] == "second"

    def test_add_child(self):
        t = make_tasks()
        t.add("parent")
        t.add("child", parent="1")
        assert "1.1" in t._tree
        assert t._tree["1.1"]["parent_id"] == "1"

    def test_add_grandchild(self):
        t = make_tasks()
        t.add("root")
        t.add("child", parent="1")
        t.add("grandchild", parent="1.1")
        assert "1.1.1" in t._tree
        assert t._tree["1.1.1"]["parent_id"] == "1.1"

    def test_add_second_child(self):
        t = make_tasks()
        t.add("parent")
        t.add("child1", parent="1")
        t.add("child2", parent="1")
        assert "1.2" in t._tree

    def test_add_invalid_parent_raises(self):
        t = make_tasks()
        with pytest.raises(RuntimeError, match="not exist"):
            t.add("orphan", parent="999")

    def test_add_prints_feedback(self, capsys):
        t = make_tasks()
        t.add("do something")
        out = capsys.readouterr().out
        assert "+ 1 " in out
        assert "do something" in out

    def test_add_child_prints_feedback(self, capsys):
        t = make_tasks()
        t.add("parent")
        _ = capsys.readouterr()  # clear
        t.add("child", parent="1")
        out = capsys.readouterr().out
        assert "+ 1.1" in out
        assert "child" in out


class TestDone:
    def test_done_current_task(self):
        t = make_tasks()
        t.add("task")
        t.done()
        assert t._tree["1"]["status"] == "done"

    def test_done_by_id(self):
        t = make_tasks()
        t.add("task")
        t.done("1")
        assert t._tree["1"]["status"] == "done"

    def test_done_nonexistent_raises(self):
        t = make_tasks()
        with pytest.raises(RuntimeError, match="not exist"):
            t.done("999")

    def test_done_no_current_raises(self):
        """done() should raise when there are no tasks."""
        t = make_tasks()
        with pytest.raises(RuntimeError, match="No task"):
            t.done()

    def test_done_auto_advances_current(self, capsys):
        t = make_tasks()
        t.add("parent")
        t.add("child1", parent="1")
        t.add("child2", parent="1")
        _ = capsys.readouterr()
        t.done()  # done 1.1 (auto-selected leaf)
        out = capsys.readouterr().out
        assert "1.1" in out
        assert "[done]" in out
        assert "1.2" in out  # next current shown in feedback

    def test_done_prints_no_more_tasks(self, capsys):
        t = make_tasks()
        t.add("only one")
        _ = capsys.readouterr()
        t.done()
        out = capsys.readouterr().out
        assert "no more tasks" in out

    def test_done_prints_remaining_children(self, capsys):
        """After completing a child, feedback shows remaining children."""
        t = make_tasks()
        t.add("parent")
        t.add("child1", parent="1")
        t.add("child2", parent="1")
        _ = capsys.readouterr()
        t.done()  # done 1.1
        out = capsys.readouterr().out
        assert "1.2" in out


class TestRemove:
    def test_remove_task(self):
        t = make_tasks()
        t.add("task")
        t.remove("1")
        assert "1" not in t._tree

    def test_remove_cascades(self):
        t = make_tasks()
        t.add("parent")
        t.add("child1", parent="1")
        t.add("child2", parent="1")
        t.add("grandchild", parent="1.1")
        t.remove("1")
        assert len(t._tree) == 0

    def test_remove_child_only(self):
        t = make_tasks()
        t.add("parent")
        t.add("child1", parent="1")
        t.add("child2", parent="1")
        t.remove("1.1")
        assert "1" in t._tree
        assert "1.1" not in t._tree
        assert "1.2" in t._tree

    def test_remove_nonexistent_raises(self):
        t = make_tasks()
        with pytest.raises(RuntimeError, match="not exist"):
            t.remove("999")

    def test_remove_prints_feedback(self, capsys):
        t = make_tasks()
        t.add("parent")
        t.add("child", parent="1")
        _ = capsys.readouterr()
        t.remove("1")
        out = capsys.readouterr().out
        assert "x" in out
        assert "subtask" in out


class TestList:
    def test_list_empty(self, capsys):
        t = make_tasks()
        t.list()
        out = capsys.readouterr().out
        assert "no tasks" in out

    def test_list_tree_structure(self, capsys):
        t = make_tasks()
        t.add("parent")
        t.add("child1", parent="1")
        t.add("child2", parent="1")
        _ = capsys.readouterr()
        t.list()
        out = capsys.readouterr().out
        assert "1 " in out or "1." in out
        assert "1.1" in out
        assert "1.2" in out

    def test_list_shows_done(self, capsys):
        t = make_tasks()
        t.add("task")
        t.done()
        _ = capsys.readouterr()
        t.list()
        out = capsys.readouterr().out
        assert "[done]" in out


class TestCurrent:
    def test_current_single_task(self):
        t = make_tasks()
        t.add("task")
        assert t._current() == "1"

    def test_current_selects_first_undone_leaf(self):
        t = make_tasks()
        t.add("parent")
        t.add("child1", parent="1")
        t.add("child2", parent="1")
        assert t._current() == "1.1"

    def test_current_skips_done(self):
        t = make_tasks()
        t.add("parent")
        t.add("child1", parent="1")
        t.add("child2", parent="1")
        t.done("1.1")
        assert t._current() == "1.2"

    def test_current_returns_parent_when_children_done(self):
        t = make_tasks()
        t.add("parent")
        t.add("child1", parent="1")
        t.done("1.1")
        # All children done; parent becomes current
        assert t._current() == "1"

    def test_current_none_when_all_done(self):
        t = make_tasks()
        t.add("task")
        t.done("1")
        assert t._current() is None

    def test_current_empty_tree(self):
        t = make_tasks()
        assert t._current() is None

    def test_current_deep_tree(self):
        t = make_tasks()
        t.add("root")
        t.add("mid", parent="1")
        t.add("leaf", parent="1.1")
        assert t._current() == "1.1.1"


class TestSignal:
    def test_signal_empty_shows_bootstrap(self):
        """Empty task list: signal shows the pre-filled bootstrap task."""
        t = make_tasks()
        t.signal_update()
        assert t.signal != {}
        body = t.signal["tasks"]
        assert "Review current situation" in body
        assert "current:" in body

    def test_signal_with_tasks(self):
        t = make_tasks()
        t.add("do something")
        t.signal_update()
        body = t.signal["tasks"]
        assert "current: 1" in body
        assert "do something" in body

    def test_signal_tree_indentation(self):
        t = make_tasks()
        t.add("parent")
        t.add("child", parent="1")
        t.signal_update()
        body = t.signal["tasks"]
        lines = body.strip().split("\n")
        # Child task should be indented (skip lines starting with "current:")
        child_line = [l for l in lines if "1.1" in l and not l.startswith("current:")][0]
        assert child_line.startswith("  ")

    def test_signal_done_marker(self):
        t = make_tasks()
        t.add("task")
        t.done("1")
        t.signal_update()
        body = t.signal["tasks"]
        assert "[done]" in body

    def test_signal_does_not_write_namespace(self):
        """signal_update() must not write _current_task_id to namespace (P1 fix)."""
        t, ns = make_tasks_with_ns()
        t.add("task")
        # Clear ns after add() has written it, then verify signal_update() does not re-write
        ns.clear()
        t.signal_update()
        assert "_current_task_id" not in ns

    def test_isinstance_skillbase(self):
        from vessal.skills._base import BaseSkill
        t = Tasks()
        assert isinstance(t, BaseSkill)


class TestNamespaceSync:
    """Tool methods must keep ns['_current_task_id'] in sync."""

    def test_add_updates_current_task_id(self):
        t, ns = make_tasks_with_ns()
        t.add("first task")
        assert ns.get("_current_task_id") == "1"

    def test_done_updates_current_task_id(self):
        t, ns = make_tasks_with_ns()
        t.add("one")
        t.add("two")
        t.done("1")
        assert ns.get("_current_task_id") == "2"

    def test_done_all_sets_none(self):
        t, ns = make_tasks_with_ns()
        t.add("only")
        t.done("1")
        assert ns.get("_current_task_id") is None

    def test_remove_updates_current_task_id(self):
        t, ns = make_tasks_with_ns()
        t.add("one")
        t.add("two")
        t.remove("1")
        assert ns.get("_current_task_id") == "2"


class TestPrompt:
    def test_prompt_returns_tuple(self):
        t = make_tasks()
        result = t._prompt()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_prompt_mentions_sleep(self):
        _, methodology = make_tasks()._prompt()
        assert "sleep" in methodology

    def test_prompt_no_method_names(self):
        """_prompt() should not contain concrete method signatures (rule 4)."""
        _, methodology = make_tasks()._prompt()
        assert "tasks.add" not in methodology
        assert "add_task" not in methodology
        assert "tasks.done" not in methodology

    def test_prompt_mentions_guide(self):
        """_prompt() should remind Agent to check guide."""
        _, methodology = make_tasks()._prompt()
        assert "guide" in methodology
