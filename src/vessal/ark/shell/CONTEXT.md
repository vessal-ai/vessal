# Shell

Agent Carrier Layer. Shell is "a place to put an Agent" — it covers every artifact that lets the outside world reach a running Hull, across every carrier shape that Vessal supports (foreground CLI process, `vessal start --daemon` process, Docker container).

## Public Interface

Shell has three subdomains:

| Subdomain | Purpose | Files |
|-----------|---------|-------|
| Entry | How a user interacts with Vessal | `cli/` (process/skill/init subcommands — currently `cli.py`; `cli/` subpackage is a P5 deliverable) + `tui/` |
| Runtime | Which process carries the Hull | `runtime/` — Hull runtime carriers (subprocess + container) |
| Supervisor | The HTTP proxy + crash-restart watchdog that wraps subprocess mode | `server.py` |

Plus carrier-agnostic plumbing:
- `http_server.py` — stdlib `HTTPServer` base with quiet disconnect policy
- `protocol.py` — `handle()` type definitions (`HandleResult = tuple[int, dict | StaticResponse]`), shared by all Shell implementations
- `events.py` — carrier event types

## Responsible for

- Hosting the Hull subprocess (subprocess mode) or Hull in-process (container mode)
- Parsing HTTP and forwarding to `Hull.handle()` via `HullHttpHandlerBase`
- Crash detection + auto-restart (supervisor, subprocess mode only)
- CLI entry (`vessal` console script)

Not responsible for:
- Business logic (Hull)
- Frame execution (Cell)
- Skill management (Hull)
- Heartbeat scheduling (handled by the `heartbeat` skill)

## Constraints

1. Shell does not import Cell or Kernel — dependency direction: Shell depends on Hull, Hull depends on Cell, no reverse
2. All public classes and functions must have complete docstrings and type annotations
3. Shell only interacts with Hull via Hull.handle(); it does not access Hull's internal attributes

## Design

Subprocess mode = foreground + `--daemon` CLI. The main process runs `ShellServer` (HTTP proxy + `_ProxyHandler` + watchdog thread); it `subprocess.Popen`s `runtime/subprocess_mode.py` which creates `Hull`, binds 127.0.0.1 on an internal port, and forwards each request through `SubprocessHullHandler` (a subclass of `HullHttpHandlerBase`). Crash isolation: native-library segfaults kill only the Hull child; the supervisor restarts it and returns HTTP 503 in the interim.

Container mode = Docker `ENTRYPOINT`. There is no `ShellServer` — the container itself is the supervisor (restarts are Docker's job). `runtime/container_mode.py` directly constructs `Hull`, binds 0.0.0.0, and runs `ContainerHullHandler` (also a subclass of `HullHttpHandlerBase`) on the user-visible port. A `SIGTERM` handler shuts Hull down gracefully; `/healthz` is a handler-level bypass for Docker's HEALTHCHECK. A first-boot step (`sync_image_to_volume`) seeds the volume from the baked `/opt/agent-image/`.

The two carriers share exactly one base class (`HullHttpHandlerBase`) that owns `do_GET`, `do_POST`, `_read_json`, and `_respond`. Differences between carriers are declared by subclass overrides (HOST, healthz path, logging, lifecycle hooks) — nothing is duplicated.

Shell depends on Hull; Hull does not know Shell exists. `TYPE_CHECKING` blocks avoid runtime circular imports.

## Status

### TODO
- [ ] 2026-04-09: The companion process startup logic in `_cmd_start` in cli.py is too long; consider extracting

### Known Issues
- 2026-04-09: cli.py is currently 739 lines, exceeding the 500-line convention (not set as a hard constraint because the centralized CLI entry design requires a longer file)
- 2026-04-10: Daemon lifecycle identity model rebuild — PID file replaced with flock (data/vessal.lock); see flock identity model plan

### Active
- 2026-04-10: Refactor start/stop to flock identity model: foreground by default, --daemon optional for background, stop waits for process exit

### Completed
- 2026-04-10: Shell-Hull process isolation — Hull runs in a subprocess (subprocess.Popen runtime/subprocess_mode.py), Shell main process acts as HTTP gateway and guardian, including crash detection and auto-restart
