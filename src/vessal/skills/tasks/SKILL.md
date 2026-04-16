---
name: tasks
description: Hierarchical task management
---

# tasks

Tree-structured task list. Hierarchical numeric IDs; current task is auto-selected.

## Methods

tasks.add(goal, parent=None) — Add a task. parent=None creates a root task; parent="1" creates a subtask under task 1
tasks.done(task_id=None) — Mark as complete. Defaults to completing the current task (the first incomplete leaf, auto-selected)
tasks.remove(task_id) — Delete a task and all its subtasks
tasks.list() — Print the full task tree

## Rules

IDs are hierarchical numbers: root tasks are "1"/"2", subtasks are "1.1"/"1.2", grandchildren are "1.1.1".
Current task = the first incomplete leaf node in numeric order, auto-selected by the system.
remove cascades to delete all subtasks.
