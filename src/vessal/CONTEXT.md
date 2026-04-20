# Vessal

LLM-driven Agent runtime. Implements the SORA model (State, Observation, Reasoning, Action) and provides a hostable execution environment for Agent applications.

Responsible for:
- Exposing the top-level API (Cell, Core, Hull)
- Unified CLI entry point (`vessal` command)
- Exporting ARK core types for external consumers

Not responsible for:
- HTTP serving (→ `ark/shell/`)
- Agent orchestration logic (→ `ark/shell/hull/`)
- Single-frame computation (→ `ark/shell/hull/cell/`)
- Specific Skill implementations (→ `skills/`)

## Constraints

1. `__init__.py` only re-exports; contains no logic
2. `cli.py` only operates the runtime via Shell / Hull public APIs; does not access internal modules directly
3. Dependency direction is fixed: Shell → Hull → Cell, no reverse direction → `tests/architecture/test_dependency_direction.py`

## Design

Vessal exists to provide a unified Agent runtime so that application developers do not need to worry about frame scheduling, event loops, Skill lifecycle, or other low-level mechanisms — they can write Skills directly toward task goals. Without Vessal, every Agent project would need to independently solve state persistence, wake scheduling, LLM call management, and other concerns, resulting in large amounts of duplicated and non-reusable infrastructure code.

The project top level (`src/vessal/`) is the outward-facing facade of the entire package, not a feature implementation layer. It does only two things: re-exports ARK core types, and provides the CLI entry point. All real runtime logic sinks into the ARK subsystem. This design choice is intentional — top-level stability takes priority over flexibility; external consumers' `from vessal import Hull` import path does not change due to internal refactoring.

The alternative of placing the CLI implementation directly at the top level was rejected. CLI runtime commands (start, stop, send, etc.) need to access the Shell layer; developer tool commands (init, skill) need to access project scaffolding logic — neither belongs to the top-level responsibility. The current design delegates the implementation to `ark/shell/cli`, with the top level holding only the `main()` dispatch entry point, maintaining the invariant of no business logic at the top level.

Invariants: `__init__.py`'s `__all__` must stay in sync with ARK exports. The top level does not introduce new runtime dependencies. All CLI subcommand implementations live inside ARK; the top-level `cli.py` only does lazy-load forwarding.

Relationship between the two subsystems: ARK (`ark/`) is the runtime core; Skills (`skills/`) is the capability layer. ARK provides mechanism; Skills provide policy. The top level accesses both through public interfaces only, without reaching into their internals. See architecture details → `references/whitepaper/02-architecture.md`.

```mermaid
graph TD
    subgraph vessal["vessal package (outward-facing facade)"]
        CLI["cli.py — CLI entry point"]
        API["__init__.py — re-export public types"]
    end

    subgraph ARK["ark/ — runtime core"]
        Shell["shell/ — HTTP boundary layer (main process)"]
        Hull["hull/ — Agent orchestration layer (subprocess)"]
        Cell["cell/ — single-frame execution engine (subprocess)"]
        Util["util/ — shared utilities (stateless)"]
    end

    subgraph Skills["skills/ — capability layer"]
        chat["chat"]
        tasks["tasks"]
        memory["memory"]
        pin["pin"]
        heartbeat["heartbeat"]
    end

    CLI --> Shell
    API --> ARK
    Shell --> Hull
    Hull --> Cell
    Shell -.->|"import (utilities)"| Util
    Hull -.->|"import (utilities)"| Util
    Cell -.->|"import (utilities)"| Util
    Hull -->|"load Skill"| Skills
```

### Process Architecture

Shell and Hull run in different OS processes. The process boundary is drawn between them because exec() may trigger native crashes that must be isolated from the HTTP service.

```mermaid
flowchart TB
    ExternalWorld -->|"HTTP :8420"| Shell

    subgraph MainProcess["Main Process — Shell"]
        Shell["Gateway + Guardian"]
    end

    Shell -->|"handle(method, path, body)\nreverse proxy · process boundary"| Hull

    subgraph SubProcess["Subprocess — agent/.venv/bin/python"]
        Hull["Hull Orchestrator"]
        EL["EventLoop\nevent loop"]
        SM["SkillManager\ndiscovery + loading"]
        Cell["Cell\nsingle-frame execution"]
        Kernel["Kernel\nnamespace + exec()"]
        Gate["Gate\nstate/action validation"]
        SkillSrv["Skill Servers\ncontinuously running"]

        Hull --> EL
        Hull --> SM
        EL -->|"step()"| Cell
        Cell --> Kernel
        Cell --> Gate
        SM -->|"load/unload"| SkillSrv
        SM -->|"cell.set(name, instance)"| Kernel
    end

    Kernel <-->|"Ping / Pong"| LLM["LLM API"]
    Shell -.->|"crash → restart\nrestore(snapshot)"| SubProcess
```

### Data Flow: A Single HTTP Request

How an external request flows through the three layers after it arrives.

```mermaid
sequenceDiagram
    participant W as External World
    participant S as Shell (main process)
    participant H as Hull (subprocess)
    participant SK as Skill Server

    W->>S: HTTP request
    S->>H: handle(method, path, body)

    alt System routes (/status, /wake, /stop)
        H-->>S: (status, dict)
    else Skill routes (/skills/{name}/...)
        H->>SK: forward to handler
        SK-->>H: response
        H-->>S: (status, dict)
    end

    S-->>W: HTTP response
```

### Data Flow: A Single Frame Execution

The event-driven frame execution process.

```mermaid
sequenceDiagram
    participant EL as EventLoop
    participant K as Kernel
    participant G as Gate
    participant C as Core (LLM)
    participant NS as Namespace

    EL->>NS: _wake = reason, _sleeping = False

    loop Frame loop (until sleep or max_frames)
        K->>NS: scan _signal()
        K->>K: render Ping
        K->>G: state_gate check
        G-->>K: pass
        K->>C: Ping
        C-->>K: Pong (think + action)
        K->>G: action_gate check
        G-->>K: pass
        K->>NS: exec(code)
        K->>K: commit frame record
    end

    NS-->>EL: _sleeping = True
```

### Skill's Position in the System

Skill spans both the Cell and Hull layers and acts as a two-sided interface between the Agent and the outside world.

```mermaid
flowchart LR
    subgraph Cell_Side["Cell side — inside Namespace"]
        SK["Skill instance\nname · tool · signal"]
    end

    subgraph Hull_Side["Hull side — outside frame loop"]
        SV["Skill Server\nHTTP · timer · UI"]
    end

    Agent["Agent\n(LLM exec code)"] -->|"skill.tool()"| SK
    SK -->|"_signal() → Ping"| Agent
    ExternalWorld -->|"HTTP /skills/{name}/..."| SV
    SV -->|"write shared data"| SK
    SK <-->|"shared mutable / HTTP / NS keys"| SV
```

### Agent Event Loop State Machine

The Hull event loop alternates between sleeping and executing.

```mermaid
stateDiagram-v2
    [*] --> Sleeping

    Sleeping --> Waking : event arrives (message / timer / manual)
    Waking --> FrameExecution : set _wake, load prompts

    state FrameExecution {
        [*] --> signal
        signal --> render : scan _signal()
        render --> state_gate
        state_gate --> LLMCall : pass
        LLMCall --> action_gate
        action_gate --> exec : pass
        exec --> commit : commit frame record
        commit --> [*]
    }

    FrameExecution --> FrameExecution : _sleeping=False and max_frames not reached
    FrameExecution --> Sleeping : sleep() or max_frames
    FrameExecution --> Snapshot : crash recovery
    Snapshot --> Sleeping : restore complete
```

## Status

### TODO
None.

### Known Issues
None.

### Active
None.
