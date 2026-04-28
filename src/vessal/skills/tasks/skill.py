"""tasks Skill — hierarchical task management.

Tree-structured tasks with hierarchical numeric IDs; current task selected automatically.
"""
from __future__ import annotations

from vessal.skills._base import BaseSkill


class Tasks(BaseSkill):
    """Hierarchical task management Skill."""

    name = "tasks"
    description = "hierarchical tasks"

    def __init__(self) -> None:
        super().__init__()
        self._ns: dict | None = None
        self._tree: dict[str, dict] = {}
        print("tasks: add(title)/done(id)/list() — task management")

    # ── Internal utilities ──

    def _children(self, task_id: str) -> list[str]:
        """Return a sorted list of direct child task IDs for task_id."""
        prefix = task_id + "."
        return sorted(
            (tid for tid in self._tree
             if tid.startswith(prefix) and "." not in tid[len(prefix):]),
            key=self._sort_key,
        )

    def _descendants(self, task_id: str) -> list[str]:
        """Return all descendant IDs of task_id (including itself)."""
        prefix = task_id + "."
        return [task_id] + sorted(
            tid for tid in self._tree if tid.startswith(prefix)
        )

    def _next_child_id(self, parent_id: str | None) -> str:
        """Compute the ID for the next child task."""
        if parent_id is None:
            # Root task: find the largest numeric key
            root_keys = [int(k) for k in self._tree if k.isdecimal()]
            return str(max(root_keys) + 1) if root_keys else "1"
        # Child task
        children = self._children(parent_id)
        if not children:
            return f"{parent_id}.1"
        last_num = int(children[-1].split(".")[-1])
        return f"{parent_id}.{last_num + 1}"

    @staticmethod
    def _sort_key(tid: str) -> list[int]:
        """Hierarchical sort key: "1.2.10" → [1, 2, 10]."""
        return [int(x) for x in tid.split(".")]

    def _current(self) -> str | None:
        """Auto-select the current task: first undone leaf node in numeric order."""
        active = sorted(
            (tid for tid, node in self._tree.items()
             if node["status"] != "done"),
            key=self._sort_key,
        )
        for tid in active:
            children = self._children(tid)
            undone_children = [c for c in children if self._tree[c]["status"] != "done"]
            if not undone_children:
                # Leaf node, or all children are done
                return tid
        return None

    def _sync_current_task_id(self) -> None:
        """Write _current_task_id to namespace if ns is available."""
        if self._ns is not None:
            self._ns["_current_task_id"] = self._current()

    # ── Public API ──

    def add(self, goal: str, parent: str | None = None) -> str:
        """Add a task.

        Args:
            goal: Task goal description.
            parent: Parent task ID. None creates a root task.

        Returns:
            Hierarchical numeric ID of the new task.

        Raises:
            RuntimeError: parent does not exist.
        """
        if parent is not None and parent not in self._tree:
            raise RuntimeError(f"Parent task {parent!r} does not exist")

        new_id = self._next_child_id(parent)
        self._tree[new_id] = {
            "id": new_id,
            "goal": goal,
            "status": "active",
            "parent_id": parent,
        }
        print(f"+ {new_id} {goal}")
        self._sync_current_task_id()
        return new_id

    def done(self, task_id: str | None = None) -> None:
        """Mark a task as complete.

        Args:
            task_id: ID of the task to complete. None completes the current task (auto-selected).

        Raises:
            RuntimeError: task_id does not exist, or there is no current task.
        """
        if task_id is None:
            task_id = self._current()
            if task_id is None:
                raise RuntimeError("No task to complete")

        if task_id not in self._tree:
            raise RuntimeError(f"Task {task_id!r} does not exist")

        node = self._tree[task_id]
        node["status"] = "done"

        # Feedback
        next_current = self._current()
        print(f"v {task_id} {node['goal']} [done]")
        if next_current:
            print(f"current: {next_current} {self._tree[next_current]['goal']}")
        else:
            print("(no more tasks)")
        self._sync_current_task_id()

    def remove(self, task_id: str) -> None:
        """Delete a task and all its subtasks.

        Args:
            task_id: ID of the task to delete.

        Raises:
            RuntimeError: task_id does not exist.
        """
        if task_id not in self._tree:
            raise RuntimeError(f"Task {task_id!r} does not exist")

        to_remove = self._descendants(task_id)
        goal = self._tree[task_id]["goal"]
        child_count = len(to_remove) - 1

        for tid in to_remove:
            del self._tree[tid]

        suffix = f" (including {child_count} subtask(s))" if child_count > 0 else ""
        print(f"x deleted {task_id} {goal}{suffix}")
        self._sync_current_task_id()

    def list(self) -> None:
        """Print the full task tree."""
        if not self._tree:
            print("(no tasks)")
            return

        def _render_tree(parent_id: str | None, indent: int) -> list[str]:
            children = sorted(
                (tid for tid, node in self._tree.items()
                 if node["parent_id"] == parent_id),
                key=self._sort_key,
            )
            lines = []
            for tid in children:
                node = self._tree[tid]
                status = " [done]" if node["status"] == "done" else ""
                prefix = "  " * indent
                lines.append(f"{prefix}{tid} {node['goal']}{status}")
                lines.extend(_render_tree(tid, indent + 1))
            return lines

        print("\n".join(_render_tree(None, 0)))

    # ── Bootstrap prompt ──

    def _ensure_bootstrap(self) -> None:
        """Pre-fill a bootstrap task when the task list is empty."""
        if not self._tree:
            self._tree["1"] = {
                "id": "1",
                "goal": "Review current situation and plan tasks",
                "status": "active",
                "parent_id": None,
            }

    # ── Signal ──

    def signal_update(self) -> None:
        """Per-frame: render task tree + current task."""
        self._ensure_bootstrap()

        lines = []

        current = self._current()
        if current:
            lines.append(f"current: {current} {self._tree[current]['goal']}")
        else:
            lines.append("(all tasks complete)")
        lines.append("")

        def _render(parent_id: str | None, indent: int) -> None:
            children = sorted(
                (tid for tid, node in self._tree.items()
                 if node["parent_id"] == parent_id),
                key=self._sort_key,
            )
            for tid in children:
                node = self._tree[tid]
                status = " [done]" if node["status"] == "done" else ""
                prefix = "  " * indent
                lines.append(f"{prefix}{tid} {node['goal']}{status}")
                _render(tid, indent + 1)

        _render(None, 0)
        text = "\n".join(lines)
        self.signal = {"tasks": text} if text else {}

    # ── Prompt ──

    def _prompt(self) -> tuple[str, str] | None:
        """Cognitive protocol: guide the Agent to use the task system."""
        return (
            "receiving a work request or starting a multi-step operation",
            "The task system is your work roadmap.\n"
            "When given work, first create a root task describing the goal, then start.\n"
            "If the goal is too large to do directly, break it into subtasks.\n"
            "Always work on the current task only — the system auto-selects the first undone leaf.\n"
            "Mark done when finished; the system advances to the next automatically.\n"
            "When all tasks are complete, sleep.\n"
            "Before first use, print(tasks.guide) to see available methods."
        )
