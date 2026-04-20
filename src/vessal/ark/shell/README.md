# Shell

HTTP boundary layer. Parses external HTTP requests and proxies them to Hull, then returns Hull's responses to the caller.

## Design

Shell exists for two reasons. First, to isolate HTTP protocol details from Hull — Hull only sees a `(method, path, body_dict)` triple and knows nothing about HTTP headers or JSON encoding/decoding. Second, to provide process-level crash isolation — Shell runs in the main process, Hull runs in a subprocess (started via `subprocess.Popen` running `hull_runner.py` with `sys.executable`). LLM-generated code executes inside the Hull subprocess; fatal errors from native libraries (abort, segfault) only kill the subprocess. Shell's guardian thread detects subprocess exit and automatically restarts it, returning "agent restarting" to callers in the interim — users see a temporary HTTP 503 rather than "connection refused". Shell is to Hull what Docker is to the application running inside the container.

Steps for Shell to start the Hull subprocess: call `_spawn_hull()`, which starts `hull_runner.py` as a subprocess and waits for stdout to output a `READY:{port}` message (indicating the Hull internal HTTP service is ready), then `_ProxyHandler` begins forwarding requests to Hull's internal port. Before starting, Shell launches a guardian thread (monitor) that periodically checks subprocess status; if it finds the process has died, it automatically calls `_spawn_hull()` to restart.

```mermaid
sequenceDiagram
    participant CLI
    participant Shell
    participant HullSubprocess as Hull subprocess

    CLI->>Shell: ShellServer.start()
    Shell->>HullSubprocess: subprocess.Popen(hull_runner.py)
    HullSubprocess-->>Shell: stdout: READY:{port}
    Shell->>Shell: start guardian thread (monitor)
    Shell->>Shell: start HTTP server

    loop Each HTTP request
        Note over Shell: User request arrives
        Shell->>HullSubprocess: reverse proxy forward request
        HullSubprocess-->>Shell: response
        Shell-->>CLI: response returned to caller
    end

    Note over Shell,HullSubprocess: If subprocess crashes
    HullSubprocess--xShell: process exits
    Shell->>Shell: monitor detects death
    Shell->>HullSubprocess: _spawn_hull() restart
    Note over Shell: returns 503 during restart
```

Shell is a pure proxy and makes no routing decisions. It receives a request and forwards it as-is to the Hull subprocess (reverse proxy), without knowing what routes exist. The routing table lives inside Hull; Shell does not hold a copy.

ShellServer has three public methods: `start()` (non-blocking: starts HTTP thread + starts Hull subprocess + starts guardian thread), `serve_forever()` (blocks until shutdown is called), `shutdown()` (stops all threads + kills subprocess).

Decision to remove heartbeat scheduling from Shell: early versions of ShellServer held a heartbeat timer, but the timer is an Agent behavioral policy (how often to wake), not an HTTP protocol concern. Moving it to the heartbeat Skill made Shell stateless — it has no timers to initialize (only a guardian timer), no business background threads, and no scheduling side effects to worry about in tests.

Invariants: Every request that reaches the Shell HTTP server, regardless of path or method, must be forwarded to the Hull subprocess's HTTP service. Shell must not short-circuit before forwarding (except for protocol-level errors, such as body being None when Content-Length is missing, which will still be attempted). If the Hull subprocess is unavailable (during a crash), Shell returns 503 Service Unavailable.

Shell and Hull relationship: Shell depends on Hull; Hull does not know Shell exists. Type annotations use `TYPE_CHECKING` blocks to avoid runtime circular imports.

## Public Interface

### class ShellServer

Shell HTTP gateway + Hull subprocess guardian.


## Tests

- `test_protocol.py` — Test Shell↔Hull protocol type definitions.
- `test_proxy.py` — test_proxy.py — Unit tests for the Shell reverse proxy.
- `test_server.py` — test_server — Shell HTTP endpoint tests (forwarded via _ProxyHandler to a fake backend).
- `test_shell_scheduler.py` — test_shell_scheduler — heartbeat skill server timer tests.
- `test_supervisor.py` — test_supervisor.py — Integration tests for ShellServer subprocess management.

Run: `uv run pytest src/vessal/ark/shell/tests/`


## Status

### TODO
- [ ] 2026-04-09: The companion process startup logic in `_cmd_start` in cli.py is too long; consider extracting

### Known Issues
None.

### Active
None.
