# Tasks

Hierarchical task tree management Skill. Tree structure + auto focus + minimal API.

Responsible for:
- Hierarchical task CRUD (add/done/remove/list)
- Automatic hierarchical ID assignment ("1", "1.1", "1.1.1")
- Auto-selection of current task (first incomplete leaf node)
- Pre-filling guidance tasks on wake-up
- Rendering task tree + current task each frame (_signal)
- Injecting cognitive protocol (_prompt, methodology only, no method names)

Not responsible for:
- Task persistence
- Dependencies (blocked_by, future version)
- Task assignment and scheduling

## Design

### Map Philosophy

Agent's task tree is its map, and also its life. Any action Agent takes must follow the map — no action without a map. The map can be modified at any time, but must always exist.

### Theoretical Framework

Four theories support the design of Tasks:

**GTD (Getting Things Done)** — project/next-action separation. Root task = project (multi-step outcome), child task = next action (smallest executable step). Tasks forces Agent to build the project first, then decompose.

**HTN (Hierarchical Task Network)** — abstract→primitive lazy decomposition. Agent does not need to plan all sub-tasks at once; can discover them as it proceeds.

**Kanban WIP=1** — at most one in-progress task at any time. Claude Code, Codex both use this hard constraint.

**DFS/LIFO** — depth-first execution. Current task is always the deepest incomplete leaf. Automatically moves to the next one after completion.

```mermaid
flowchart TD
    Start["Received work request"] --> Add["add(goal) create root task"]
    Add --> Split{"Goal directly executable?"}
    Split -->|"too large"| AddChild["add(sub-goal, parent=id)"]
    AddChild --> Split
    Split -->|"yes"| Execute["Execute code"]
    Execute --> Done["done() mark complete"]
    Done --> More{"More incomplete tasks?"}
    More -->|"yes"| Execute
    More -->|"no"| Sleep["sleep()"]
```

### Hierarchical Numbering

ID format "1.2.3" — the 3rd sub-task of the 2nd sub-task of the 1st project. The ID itself encodes the hierarchy; structure is visible when copied anywhere. No tree connectors or special formatting needed.

### Auto Focus

Current task = the first leaf node with status != "done", sorted by number. Agent does not need to manually manage focus. After done(), the system automatically moves to the next one.

## Public Interface

### class Tasks

Hierarchical task management Skill.


## Tests

- `test_tasks.py` — test_tasks — Tasks Skill redesign tests.

Run: `uv run pytest src/vessal/skills/tasks/tests/`


## Status

### TODO
None.

### Known Issues
None.

### Active
None.
